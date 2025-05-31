#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
core/orchestration/conductor.py - VERSION FINALE CORRIGÉE ANTI-CHANGEMENT FENÊTRE

CORRECTIONS :
- Suppression de force_focus qui cause l'erreur
- Empêchement du changement de fenêtre lors ouverture console
- Optimisation de l'activation navigateur
"""

import threading
import time
import queue
import os
import json
import random
import pyautogui
import pyperclip
from datetime import datetime
from utils.logger import logger
from utils.exceptions import OrchestrationError, SchedulingError
from core.orchestration.state_automation import StateBasedAutomation

try:
    import pygetwindow as gw

    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False


def random_sleep(base_time, min_variance=0.05, max_variance=0.20):
    """Sleep avec variation aléatoire de +/- 5-20%"""
    variance = random.uniform(min_variance, max_variance)
    if random.choice([True, False]):
        actual_time = base_time * (1 + variance)
    else:
        actual_time = base_time * (1 - variance)
    time.sleep(max(0.1, actual_time))  # Minimum 0.1s
    return actual_time


class AIConductor:
    """Chef d'orchestre FINAL - ANTI-CHANGEMENT FENÊTRE avec timing aléatoire"""

    def __init__(self, config_provider, scheduler, database=None):
        """Initialise le chef d'orchestre"""
        self.config_provider = config_provider
        self.scheduler = scheduler
        self.database = database

        # Initialiser les contrôleurs
        from core.interaction.mouse import MouseController
        from core.interaction.keyboard import KeyboardController

        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()

        # Initialiser l'automatisation basée sur l'état
        self.state_automation = StateBasedAutomation(
            None, self.mouse_controller, self.keyboard_controller, self
        )

        # Registre des tâches et threading
        self.active_tasks = {}
        self.task_counter = 0
        self.task_queue = queue.Queue()
        self.lock = threading.RLock()
        self._shutdown = False
        self.worker_thread = None

        # Configuration
        self.console_timeout = 2
        self.extraction_retries = 2
        self.validation_timeout = 2

        # FLAG ANTI-DUPLICATION
        self.browser_already_active = False

        logger.info("Chef d'orchestre FINAL ANTI-CHANGEMENT FENÊTRE initialisé")

    def initialize(self):
        """Initialise le système"""
        try:
            # Démarrer le worker thread
            self.worker_thread = threading.Thread(target=self._worker_loop)
            self.worker_thread.daemon = True
            self.worker_thread.start()

            logger.info("Système initialisé")
            return True
        except Exception as e:
            logger.error(f"Erreur initialisation: {str(e)}")
            raise OrchestrationError(f"Échec initialisation: {str(e)}")

    # ==============================
    # TEST PRINCIPAL FINAL
    # ==============================

    def test_platform_connection_ultra_robust(self, platform_name, test_message="Bonjour ! Test.",
                                              timeout=30, wait_for_response=12, skip_browser=True):
        """Test FINAL avec gestion browser_type"""
        start_time = time.time()
        test_id = f"test_{platform_name}_{int(start_time)}"

        logger.info(f"🚀 Test FINAL démarré pour {platform_name} [ID: {test_id}] skip_browser={skip_browser}")

        try:
            # ÉTAPE 1: Validation de la configuration
            logger.info("📋 Étape 1: Validation configuration")
            config_result = self._validate_platform_configuration(platform_name)
            if not config_result['valid']:
                return {
                    'success': False,
                    'error': 'configuration_invalid',
                    'message': config_result['message'],
                    'test_id': test_id,
                    'duration': time.time() - start_time
                }

            profile = config_result['profile']
            browser_config = profile.get('browser', {})

            # DÉTECTER LE TYPE DE NAVIGATEUR
            browser_type = self._detect_browser_type_from_profile(profile)
            logger.info(f"🌐 Type de navigateur détecté: {browser_type}")

            # CONFIGURER LE STATE_AUTOMATION
            if hasattr(self.state_automation, 'browser_type'):
                self.state_automation.browser_type = browser_type
                logger.info(f"✅ State_automation configuré avec browser_type: {browser_type}")

            # ÉTAPE 2: Gestion navigateur
            if not skip_browser:
                logger.info("🌐 Étape 2: Activation navigateur")
                browser_result = self._activate_browser_robust(
                    browser_type,
                    browser_config.get('path', ''),
                    browser_config.get('url'),
                    fullscreen=True
                )
                if not browser_result['success']:
                    return {
                        'success': False,
                        'error': 'browser_activation_failed',
                        'message': browser_result['message'],
                        'test_id': test_id,
                        'duration': time.time() - start_time
                    }
                self.browser_already_active = True
            else:
                logger.info("🔄 Étape 2: Skip navigateur - Gestion URL")
                self._handle_browser_skip(browser_config)

            # ÉTAPE 3: StateAutomation fait TOUT
            logger.info("💬 Étape 3: StateAutomation fait TOUT (prompt + attente + extraction)")
            automation_params = {
                'test_text': test_message,
                'skip_browser_activation': True
            }

            automation_result = self._execute_state_automation_corrected(profile, automation_params, timeout,
                                                                         browser_type)
            if not automation_result['success']:
                return {
                    'success': False,
                    'error': 'automation_failed',
                    'message': automation_result['message'],
                    'test_id': test_id,
                    'duration': time.time() - start_time
                }

            # SUCCÈS COMPLET
            total_duration = time.time() - start_time
            response_text = automation_result.get('response', '')

            logger.info(f"✅ Test FINAL réussi en {total_duration:.1f}s")
            logger.info(f"🎉 RÉPONSE RÉCUPÉRÉE: {len(response_text)} caractères")
            logger.info(f"📝 APERÇU RÉPONSE: {response_text[:200]}..." if len(
                response_text) > 200 else f"📝 RÉPONSE COMPLÈTE: {response_text}")

            return {
                'success': True,
                'message': f"Test réussi en {total_duration:.1f}s",
                'response': response_text,
                'test_id': test_id,
                'duration': total_duration,
                'metadata': {
                    'automation_duration': automation_result.get('duration', 0),
                    'response_length': len(response_text),
                    'extraction_method': 'state_automation_internal',
                    'browser_skipped': skip_browser,
                    'browser_type': browser_type
                }
            }

        except Exception as e:
            logger.error(f"❌ Erreur test FINAL {test_id}: {str(e)}")
            return {
                'success': False,
                'error': 'unexpected_error',
                'message': str(e),
                'test_id': test_id,
                'duration': time.time() - start_time
            }

    def _detect_browser_type_from_profile(self, profile):
        """Détecte le type de navigateur depuis le profil"""
        try:
            browser_config = profile.get('browser', {})
            browser_path = browser_config.get('path', '').lower()
            browser_type = browser_config.get('type', '').lower()
            browser_url = browser_config.get('url', '').lower()

            # Priorité au type explicite
            if browser_type:
                if 'firefox' in browser_type:
                    return 'firefox'
                elif 'chrome' in browser_type:
                    return 'chrome'
                elif 'edge' in browser_type:
                    return 'edge'

            # Détection par le chemin
            if browser_path:
                if 'firefox' in browser_path or 'mozilla' in browser_path:
                    return 'firefox'
                elif 'chrome' in browser_path:
                    return 'chrome'
                elif 'edge' in browser_path:
                    return 'edge'
                elif 'safari' in browser_path:
                    return 'safari'
                elif 'opera' in browser_path:
                    return 'opera'
                elif 'brave' in browser_path:
                    return 'brave'

            # Détection par l'URL
            if browser_url:
                if 'firefox' in browser_url:
                    return 'firefox'
                elif 'chrome' in browser_url:
                    return 'chrome'

            return 'chrome'  # Par défaut

        except Exception as e:
            logger.error(f"Erreur détection browser_type: {e}")
            return 'chrome'

    def _execute_state_automation_corrected(self, profile, automation_params, timeout, browser_type='chrome'):
        """StateAutomation CORRIGÉ avec browser_type"""
        try:
            automation_result = None
            automation_start = time.time()

            # FONCTION CORRIGÉE avec 4 paramètres
            def on_automation_completed(success, message, duration, response):
                nonlocal automation_result
                automation_result = {
                    'success': success,
                    'message': message,
                    'duration': duration,
                    'response': response
                }

                logger.info(f"🔍 DEBUG on_automation_completed:")
                logger.info(f"  - Success: {success}")
                logger.info(f"  - Message: {message}")
                logger.info(f"  - Duration: {duration:.1f}s")
                logger.info(f"  - Response length: {len(response)} caractères")
                logger.info(f"  - Response preview: {response[:150]}..." if len(
                    response) > 150 else f"  - Full response: {response}")

            # Connecter le signal
            self.state_automation.automation_completed.connect(on_automation_completed)

            browser_config = profile.get('browser', {})
            if automation_params is None:
                automation_params = {}

            logger.info(f"🚀 Démarrage StateAutomation avec browser_type: {browser_type}")

            # Démarrer l'automatisation
            self.state_automation.start_test_automation(
                profile, 0, browser_type,  # Utiliser le browser_type détecté
                browser_config.get('url'), automation_params
            )

            # Attendre avec timeout
            automation_timeout = min(25, timeout - 5)
            logger.info(f"⏰ Attente résultat StateAutomation (max {automation_timeout}s)")

            while automation_result is None and (time.time() - automation_start) < automation_timeout:
                time.sleep(0.1)

            # Déconnecter le signal
            try:
                self.state_automation.automation_completed.disconnect(on_automation_completed)
            except:
                pass

            if automation_result is None:
                logger.error("❌ TIMEOUT StateAutomation - Pas de résultat reçu")
                return {
                    'success': False,
                    'message': f"Timeout automatisation ({automation_timeout}s)",
                    'duration': time.time() - automation_start,
                    'response': ''
                }

            logger.info(f"✅ StateAutomation terminé - Résultat reçu")
            return automation_result

        except Exception as e:
            logger.error(f"❌ Erreur _execute_state_automation_corrected: {str(e)}")
            return {
                'success': False,
                'message': f"Erreur automatisation: {str(e)}",
                'duration': time.time() - automation_start if 'automation_start' in locals() else 0,
                'response': ''
            }

    def _handle_browser_skip(self, browser_config):
        """Gestion navigateur en mode skip avec timing aléatoire"""
        browser_found = False
        platform_url = browser_config.get('url', '')

        # Vérifier si un navigateur est ouvert
        if HAS_PYGETWINDOW:
            try:
                all_windows = gw.getAllWindows()
                browser_windows = [w for w in all_windows if
                                   any(keyword in w.title.lower() for keyword in
                                       ['chrome', 'firefox', 'edge', 'mozilla'])]
                if browser_windows:
                    logger.info(f"✅ {len(browser_windows)} fenêtre(s) navigateur trouvée(s)")
                    browser_found = True
                    self.browser_already_active = True

                    # Optimiser la fenêtre SANS CHANGER DE FOCUS
                    try:
                        window = browser_windows[-1]
                        # NE PAS ACTIVER - juste maximiser si pas déjà fait
                        if not window.isMaximized:
                            window.maximize()
                            logger.debug("Fenêtre maximisée sans activation")
                    except Exception as e:
                        logger.debug(f"Erreur optimisation: {e}")
            except Exception as e:
                logger.warning(f"Erreur vérification fenêtres: {e}")

        # Ouvrir l'URL si nécessaire
        if browser_found and platform_url:
            logger.info(f"🌐 Ouverture nouvel onglet vers {platform_url}")
            try:
                browser_type = browser_config.get('type', 'Chrome')
                if browser_type.lower() == "firefox":
                    cmd = f'start firefox "{platform_url}"'
                elif browser_type.lower() == "chrome":
                    cmd = f'start chrome "{platform_url}"'
                elif browser_type.lower() == "edge":
                    cmd = f'start msedge "{platform_url}"'
                else:
                    cmd = f'start "{platform_url}"'

                os.system(cmd)
                # CORRECTION: Réduire l'attente après ouverture d'onglet
                random_sleep(1.5, 0.10, 0.20)  # Plus court avec variation
                logger.info("✅ URL de la plateforme ouverte dans nouvel onglet")
            except Exception as e:
                logger.error(f"❌ Erreur ouverture URL: {e}")

    # ==============================
    # MÉTHODES DE DEBUG - CORRIGÉES ANTI-CHANGEMENT FENÊTRE
    # ==============================

    def _wait_for_ai_generation_mutation_observer(self, platform_name, max_wait_time):
        """Méthode MutationObserver pour StateAutomation - VERSION ANTI-CHANGEMENT FENÊTRE"""
        logger.info(f"🔍 MutationObserver ANTI-CHANGEMENT pour {platform_name} (max {max_wait_time}s)")

        try:
            return self._wait_for_ai_generation_simple_safe(platform_name, max_wait_time)
        except Exception as e:
            logger.error(f"Erreur MutationObserver: {e}")
            return {'detected': False, 'duration': max_wait_time, 'error': str(e)}

    def _wait_for_ai_generation_simple_safe(self, platform_name, max_wait_time):
        """Surveillance IA SANS CHANGEMENT DE FENÊTRE avec timing aléatoire"""
        logger.info(f"🔍 Surveillance IA SAFE pour {platform_name} (max {max_wait_time}s)")

        try:
            # NE PAS OUVRIR LA CONSOLE SI CELA CHANGE DE FENÊTRE
            # Ouvrir console JavaScript de manière SAFE
            console_opened = False
            try:
                console_opened = self._open_console_javascript_safe()
            except Exception as e:
                logger.warning(f"Console non ouverte (mode SAFE): {e}")

            if not console_opened:
                logger.warning("Console JavaScript non disponible - délai fixe SANS changement fenêtre")
                random_sleep(max_wait_time)
                return {'detected': False, 'duration': max_wait_time, 'method': 'fallback_timeout_safe'}

            # Récupérer la config personnalisée
            profile = self._get_platform_profile(platform_name)
            detection_config = profile.get('detection_config', {}) if profile else {}

            if detection_config:
                logger.info(f"✅ Utilisation config personnalisée pour {platform_name}")
                js_code = self._get_custom_detection_js(detection_config)
            else:
                logger.info(f"⚠️ Pas de config personnalisée, fallback générique pour {platform_name}")
                if 'chatgpt' in platform_name.lower():
                    js_code = self._get_chatgpt_detection_js()
                else:
                    js_code = self._get_generic_detection_js()

            # Injecter le JavaScript
            pyperclip.copy(js_code)
            self.keyboard_controller.hotkey('ctrl', 'v')
            self.keyboard_controller.press_key('enter')

            start_time = time.time()
            last_log_time = 0

            logger.info(f"JavaScript de détection injecté pour {platform_name}")

            # Surveillance avec timing aléatoire
            while time.time() - start_time < max_wait_time:
                # Récupérer les logs console
                self.keyboard_controller.hotkey('ctrl', 'a')
                self.keyboard_controller.hotkey('ctrl', 'c')
                result = pyperclip.paste()

                # Chercher le marqueur de fin
                for line in result.split('\n'):
                    if 'LIRIS_GENERATION_COMPLETE:' in line:
                        try:
                            status = line.split('LIRIS_GENERATION_COMPLETE:')[1].strip().lower()
                            if status == 'true':
                                elapsed = time.time() - start_time
                                self._close_console_javascript_safe()
                                logger.info(f"✅ Génération détectée en {elapsed:.1f}s")
                                return {
                                    'detected': True,
                                    'duration': elapsed,
                                    'method': 'javascript_detection_safe'
                                }
                        except (IndexError, ValueError):
                            continue

                # Log périodique moins fréquent
                elapsed = time.time() - start_time
                if elapsed - last_log_time >= 3.0:  # Tous les 3s au lieu de 5s
                    remaining = max_wait_time - elapsed
                    logger.info(f"🔍 Surveillance... {remaining:.0f}s restantes")
                    last_log_time = elapsed

                random_sleep(0.3, 0.05, 0.15)  # Timing aléatoire pour surveillance

            self._close_console_javascript_safe()
            elapsed = time.time() - start_time
            logger.warning(f"⏰ Timeout surveillance SAFE ({elapsed:.1f}s)")

            return {
                'detected': False,
                'duration': elapsed,
                'method': 'timeout_safe'
            }

        except Exception as e:
            logger.error(f"Erreur surveillance SAFE: {str(e)}")
            return {
                'detected': False,
                'duration': time.time() - start_time if 'start_time' in locals() else 0,
                'method': 'error_safe',
                'error': str(e)
            }

    # ==============================
    # JAVASCRIPT DETECTION/EXTRACTION
    # ==============================

    def _get_custom_detection_js(self, detection_config):
        """JavaScript de détection personnalisé"""
        primary_selector = detection_config.get('primary_selector', '')
        detection_method = detection_config.get('detection_method', 'css_selector_presence')
        platform_type = detection_config.get('platform_type', 'Generic')

        logger.info(f"🎯 Utilisation sélecteur personnalisé: {primary_selector} (méthode: {detection_method})")

        if detection_method == 'chatgpt_data_stability':
            return f'''
            (function() {{
                console.log("🎯 Détection ChatGPT personnalisée data-start/data-end");

                let lastDataState = '';
                let stableCount = 0;
                let checkInterval;

                function checkDataStability() {{
                    try {{
                        let elements = document.querySelectorAll('{primary_selector}');
                        let currentState = '';

                        elements.forEach(el => {{
                            let start = el.getAttribute('data-start') || '';
                            let end = el.getAttribute('data-end') || '';
                            currentState += start + ':' + end + ';';
                        }});

                        console.log("📊 État data personnalisé:", currentState.length, "caractères");

                        if (currentState === lastDataState && currentState.length > 0) {{
                            stableCount++;
                            console.log("🔒 Stabilité:", stableCount, "/2");  // Plus rapide

                            if (stableCount >= 2) {{  // 2 au lieu de 3 pour plus de rapidité
                                console.log("LIRIS_GENERATION_COMPLETE:true");
                                clearInterval(checkInterval);
                                return true;
                            }}
                        }} else {{
                            lastDataState = currentState;
                            stableCount = 0;
                        }}

                        return false;
                    }} catch(e) {{
                        console.log("❌ Erreur détection personnalisée:", e.message);
                        return false;
                    }}
                }}

                checkInterval = setInterval(checkDataStability, 300);  // Plus rapide

                setTimeout(() => {{
                    clearInterval(checkInterval);
                    console.log("LIRIS_GENERATION_COMPLETE:timeout");
                }}, 15000);  // Timeout plus court

                return "Détection ChatGPT personnalisée initialisée";
            }})();
            '''
        else:
            # Autres méthodes...
            return self._get_generic_detection_js()

    def _get_chatgpt_detection_js(self):
        """JavaScript de détection pour ChatGPT - VERSION RAPIDE"""
        return '''
        (function() {
            console.log("🎯 Détection ChatGPT data-start/data-end RAPIDE démarrée");

            let lastDataState = '';
            let stableCount = 0;
            let checkInterval;

            function checkDataStability() {
                try {
                    let elements = document.querySelectorAll('[data-start][data-end]');
                    let currentState = '';

                    elements.forEach(el => {
                        let start = el.getAttribute('data-start') || '';
                        let end = el.getAttribute('data-end') || '';
                        currentState += start + ':' + end + ';';
                    });

                    console.log("📊 État data:", currentState.length, "caractères");

                    if (currentState === lastDataState && currentState.length > 0) {
                        stableCount++;
                        console.log("🔒 Stabilité:", stableCount, "/2");

                        if (stableCount >= 2) {  // Plus rapide
                            console.log("LIRIS_GENERATION_COMPLETE:true");
                            clearInterval(checkInterval);
                            return true;
                        }
                    } else {
                        lastDataState = currentState;
                        stableCount = 0;
                    }

                    return false;
                } catch(e) {
                    console.log("❌ Erreur détection:", e.message);
                    return false;
                }
            }

            checkInterval = setInterval(checkDataStability, 300);  // Plus rapide

            setTimeout(() => {
                clearInterval(checkInterval);
                console.log("LIRIS_GENERATION_COMPLETE:timeout");
            }, 15000);  // Timeout plus court

            return "Détection ChatGPT RAPIDE initialisée";
        })();
        '''

    def _get_generic_detection_js(self):
        """JavaScript de détection générique - VERSION RAPIDE"""
        return '''
        (function() {
            console.log("🔍 Détection générique RAPIDE démarrée");

            let lastText = '';
            let stableCount = 0;
            let checkInterval;

            function checkTextStability() {
                try {
                    let elements = document.querySelectorAll('p, div, span');
                    let longestText = '';

                    for (let el of elements) {
                        let text = (el.textContent || '').trim();
                        if (text.length > longestText.length) {
                            longestText = text;
                        }
                    }

                    if (longestText === lastText && longestText.length > 30) {  // Seuil plus bas
                        stableCount++;
                        console.log("🔒 Stabilité texte:", stableCount, "/3");

                        if (stableCount >= 3) {  // Plus rapide
                            console.log("LIRIS_GENERATION_COMPLETE:true");
                            clearInterval(checkInterval);
                            return true;
                        }
                    } else {
                        lastText = longestText;
                        stableCount = 0;
                    }

                    return false;
                } catch(e) {
                    console.log("❌ Erreur détection:", e.message);
                    return false;
                }
            }

            checkInterval = setInterval(checkTextStability, 500);  // Plus rapide

            setTimeout(() => {
                clearInterval(checkInterval);
                console.log("LIRIS_GENERATION_COMPLETE:timeout");
            }, 12000);  // Timeout plus court

            return "Détection générique RAPIDE initialisée";
        })();
        '''

    # ==============================
    # CONSOLE JAVASCRIPT - VERSION SAFE ANTI-CHANGEMENT FENÊTRE
    # ==============================

    def _detect_browser_type(self):
        """Détecte le type de navigateur actif"""
        try:
            # D'abord essayer d'utiliser le browser_type du state_automation
            if hasattr(self.state_automation, 'browser_type'):
                browser_type = self.state_automation.browser_type
                if browser_type and browser_type != 'unknown':
                    logger.info(f"Utilisation browser_type du state_automation: {browser_type}")
                    return browser_type

            # Fallback sur détection de fenêtre
            if HAS_PYGETWINDOW:
                all_windows = gw.getAllWindows()
                for window in all_windows:
                    title = window.title.lower()
                    if 'firefox' in title or 'mozilla' in title:
                        return 'firefox'
                    elif 'chrome' in title or 'chromium' in title:
                        return 'chrome'
                    elif 'edge' in title:
                        return 'edge'

            return 'chrome'  # Par défaut
        except Exception as e:
            logger.debug(f"Erreur détection navigateur: {e}")
            return 'chrome'

    def _open_console_javascript_safe(self):
        """Ouverture console JavaScript SANS CHANGEMENT DE FENÊTRE avec timing aléatoire"""
        try:
            logger.info("🔧 Ouverture console JavaScript SAFE...")

            # NE PAS ACTIVER LA FENÊTRE - juste détecter le navigateur
            browser_type = self._detect_browser_type()
            logger.info(f"Navigateur détecté: {browser_type}")

            # Utiliser le module console_shortcuts SANS force_focus
            try:
                from config.console_shortcuts import open_console_for_browser
                # RETIRER LE PARAMÈTRE force_focus QUI CAUSE L'ERREUR
                success = open_console_for_browser(browser_type, self.keyboard_controller)
                if success:
                    logger.info("✅ Console JavaScript ouverte SAFE via console_shortcuts")
                    random_sleep(0.8, 0.05, 0.15)  # Timing aléatoire
                    return True
            except ImportError:
                logger.warning("Module console_shortcuts non disponible, utilisation méthode legacy")
            except Exception as e:
                logger.warning(f"Erreur console_shortcuts: {e}, fallback méthode legacy")

            # Méthode legacy SANS ACTIVATION DE FENÊTRE
            success = False
            if browser_type == 'firefox':
                logger.info("Tentative Firefox SAFE: Ctrl+Shift+K")
                self.keyboard_controller.hotkey('ctrl', 'shift', 'k')
                random_sleep(0.8, 0.05, 0.15)  # Timing aléatoire
                success = True
            elif browser_type in ['chrome', 'edge']:
                logger.info(f"Tentative {browser_type} SAFE: Ctrl+Shift+J")
                self.keyboard_controller.hotkey('ctrl', 'shift', 'j')
                random_sleep(0.8, 0.05, 0.15)  # Timing aléatoire
                success = True
            else:
                logger.info("Fallback F12 SAFE")
                self.keyboard_controller.press_key('f12')
                random_sleep(0.6, 0.05, 0.15)  # Timing aléatoire
                success = True

            if success:
                # Nettoyer la console avec timing aléatoire
                pyperclip.copy("console.clear();")
                self.keyboard_controller.hotkey('ctrl', 'v')
                self.keyboard_controller.press_key('enter')
                random_sleep(0.2, 0.05, 0.15)  # Timing aléatoire

                logger.info("✅ Console JavaScript ouverte SAFE")
                return True
            else:
                logger.warning("⚠️ Impossible d'ouvrir console JavaScript SAFE")
                return False

        except Exception as e:
            logger.error(f"❌ Erreur ouverture console JavaScript SAFE: {e}")
            return False

    def _close_console_javascript_safe(self):
        """Fermeture console JavaScript SAFE avec timing aléatoire"""
        try:
            # Utiliser le module console_shortcuts
            try:
                from config.console_shortcuts import close_console_for_browser
                browser_type = self._detect_browser_type()
                close_console_for_browser(browser_type, self.keyboard_controller)
                logger.debug("Console JavaScript fermée SAFE via console_shortcuts")
            except ImportError:
                # Fallback
                self.keyboard_controller.press_key('f12')
                random_sleep(0.2, 0.05, 0.15)  # Timing aléatoire
                logger.debug("Console JavaScript fermée SAFE")
        except Exception as e:
            logger.debug(f"Erreur fermeture console SAFE: {e}")

    # ==============================
    # UTILITAIRES
    # ==============================

    def _validate_platform_configuration(self, platform_name):
        """Validation configuration"""
        try:
            profile = self._get_platform_profile(platform_name)
            if not profile:
                return {
                    'valid': False,
                    'message': f"Profil {platform_name} introuvable",
                    'profile': None
                }

            missing_elements = []
            browser_config = profile.get('browser', {})
            if not browser_config.get('url'):
                missing_elements.append('URL navigateur')

            interface_positions = profile.get('interface_positions', {})
            if not interface_positions.get('prompt_field'):
                missing_elements.append('Position champ prompt')

            if missing_elements:
                return {
                    'valid': False,
                    'message': f"Éléments manquants: {', '.join(missing_elements)}",
                    'profile': profile
                }

            return {
                'valid': True,
                'message': "Configuration complète",
                'profile': profile
            }

        except Exception as e:
            return {
                'valid': False,
                'message': f"Erreur validation: {str(e)}",
                'profile': None
            }

    def _activate_browser_robust(self, browser_type, browser_path='', url='', fullscreen=False):
        """Activation navigateur"""
        try:
            if not url:
                url = "about:blank"

            # Commande selon le navigateur
            if browser_type.lower() == "firefox":
                cmd = f'start firefox "{url}"'
            elif browser_type.lower() == "chrome":
                cmd = f'start chrome "{url}"'
            elif browser_type.lower() == "edge":
                cmd = f'start msedge "{url}"'
            else:
                cmd = f'start "{browser_path}" "{url}"' if browser_path else f'start "{url}"'

            logger.info(f"🌐 Ouverture: {cmd}")
            start_time = time.time()

            os.system(cmd)
            time.sleep(3)

            if fullscreen:
                time.sleep(1)
                self._maximize_window_robust()

            elapsed = time.time() - start_time
            self.browser_already_active = True
            logger.info(f"✅ Navigateur activé en {elapsed:.1f}s")

            return {
                'success': True,
                'message': f"Navigateur activé en {elapsed:.1f}s",
                'duration': elapsed
            }

        except Exception as e:
            logger.error(f"❌ Erreur activation navigateur: {str(e)}")
            return {
                'success': False,
                'message': f"Erreur activation: {str(e)}",
                'duration': 0
            }

    def _maximize_window_robust(self):
        """Maximisation fenêtre"""
        try:
            if HAS_PYGETWINDOW:
                all_windows = gw.getAllWindows()
                browser_windows = [w for w in all_windows
                                   if any(keyword in w.title.lower()
                                          for keyword in ['chrome', 'firefox', 'edge', 'mozilla'])]

                if browser_windows:
                    window = browser_windows[0]
                    if not window.isMaximized:
                        window.maximize()
                        time.sleep(0.5)
                    else:
                        window.activate()
                    return True

            # Fallback clavier
            pyautogui.hotkey('alt', 'space')
            time.sleep(0.2)
            pyautogui.press('x')
            time.sleep(0.5)
            return True

        except Exception as e:
            logger.warning(f"Erreur maximisation: {e}")
            return False

    def _get_platform_profile(self, platform_name):
        """Récupération profil"""
        # D'ABORD essayer les profils en mémoire (mis à jour par le widget)
        profiles = self.config_provider.get_profiles()
        memory_profile = profiles.get(platform_name)

        if memory_profile and memory_profile.get('detection_config'):
            logger.info(f"✅ Profil en mémoire trouvé pour {platform_name} avec config détection")
            return memory_profile

        # ENSUITE fallback vers la base de données
        if self.database and hasattr(self.database, 'get_platform'):
            db_profile = self.database.get_platform(platform_name)
            if db_profile:
                logger.info(f"✅ Profil base de données trouvé pour {platform_name}")
                return db_profile

        # Retourner le profil en mémoire même sans detection_config
        if memory_profile:
            logger.info(f"⚠️ Profil en mémoire sans config détection pour {platform_name}")
            return memory_profile

        logger.warning(f"❌ Aucun profil trouvé pour {platform_name}")
        return None

    def get_available_platforms(self):
        """Récupération plateformes"""
        try:
            if self.database and hasattr(self.database, 'list_platforms'):
                db_platforms = self.database.list_platforms()
                if db_platforms:
                    return [p['name'] for p in db_platforms]

            profiles = self.config_provider.get_profiles()
            available = []
            for platform_name in profiles.keys():
                can_use, _ = self.scheduler.can_use_platform(platform_name)
                if can_use:
                    available.append(platform_name)

            return available
        except Exception as e:
            logger.error(f"Erreur récupération plateformes: {e}")
            return []

    def shutdown(self):
        """Arrêt"""
        try:
            self._shutdown = True

            if hasattr(self.state_automation, 'stop_automation'):
                self.state_automation.stop_automation()

            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=2)

            self.browser_already_active = False
            logger.info("Chef d'orchestre arrêté")
        except Exception as e:
            logger.error(f"Erreur arrêt: {str(e)}")

    def emergency_stop(self):
        """Arrêt d'urgence"""
        logger.warning("🚨 ARRÊT D'URGENCE")

        try:
            self._shutdown = True
            self.browser_already_active = False

            # Arrêter StateAutomation
            if hasattr(self.state_automation, 'stop_automation'):
                self.state_automation.stop_automation()

            if hasattr(self.state_automation, 'force_stop'):
                self.state_automation.force_stop = True

            # Fermer console
            try:
                self.keyboard_controller.press_key('f12')
            except:
                pass

            logger.warning("🚨 Arrêt d'urgence terminé")

        except Exception as e:
            logger.error(f"Erreur arrêt d'urgence: {e}")

    def _worker_loop(self):
        """Worker thread"""
        while not self._shutdown:
            try:
                time.sleep(1)
            except Exception as e:
                logger.error(f"Erreur worker: {e}")
                break

    # Méthodes de compatibilité
    def send_prompt(self, platform, prompt, mode="standard", priority=0, sync=False, timeout=None):
        """Envoi prompt"""
        try:
            can_use, reason = self.scheduler.can_use_platform(platform)
            if not can_use:
                raise SchedulingError(reason)

            if sync:
                result = self.test_platform_connection_ultra_robust(
                    platform, prompt, timeout or 30, 12
                )

                if result['success']:
                    return {
                        'id': self.task_counter + 1,
                        'status': 'completed',
                        'result': {
                            'response': result.get('response', ''),
                            'duration': result.get('duration', 0),
                            'metadata': result.get('metadata', {})
                        }
                    }
                else:
                    raise OrchestrationError(result['message'])

            raise NotImplementedError("Mode asynchrone à implémenter")

        except Exception as e:
            logger.error(f"Erreur envoi prompt: {str(e)}")
            raise OrchestrationError(f"Échec envoi: {str(e)}")

    def detect_platform_elements(self, platform_name, browser_type='Chrome', browser_path='', url='', fullscreen=False):
        """Détection éléments - Placeholder"""
        return {
            'success': False,
            'error': 'not_implemented',
            'message': "Détection éléments non implémentée dans cette version"
        }

    def test_platform_connection(self, platform_name, **kwargs):
        """Redirection vers version corrigée"""
        return self.test_platform_connection_ultra_robust(platform_name, **kwargs)