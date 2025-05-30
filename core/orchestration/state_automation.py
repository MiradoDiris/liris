#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
core/orchestration/state_automation.py - VERSION CORRIGÉE

Corrections principales:
- PAS d'Alt+Tab qui change de fenêtre !
- Focus par clic dans la fenêtre du navigateur
- Intégration des raccourcis console par navigateur
- Simplification de la logique d'exécution
"""

import time
import json
import pyperclip
from enum import Enum
from PyQt5.QtCore import QObject, pyqtSignal
from utils.logger import logger
from utils.exceptions import OrchestrationError
from config.console_shortcuts import console_shortcuts, open_console_for_browser, close_console_for_browser

try:
    import pygetwindow as gw

    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False


class StateBasedAutomation(QObject):
    """Automatisation simplifiée avec gestion correcte de la console"""

    # Signaux pour communication externe
    step_completed = pyqtSignal(str, str)
    automation_completed = pyqtSignal(bool, str, float, str)
    automation_failed = pyqtSignal(str, str)

    def __init__(self, detector, mouse_controller, keyboard_controller, conductor):
        super().__init__()
        self.detector = detector
        self.mouse_controller = mouse_controller
        self.keyboard_controller = keyboard_controller
        self.conductor = conductor

        # État simple
        self.is_running = False
        self.force_stop = False
        self.start_time = None

        # Configuration
        self.platform_profile = None
        self.test_text = ""
        self.skip_browser_activation = False
        self.extracted_response = ""
        self.browser_type = "chrome"  # Par défaut

        logger.info("StateBasedAutomation CORRIGÉ initialisé")

    def start_test_automation(self, platform_profile, num_tabs, browser_type, url, automation_params=None):
        """Démarre l'automatisation avec gestion correcte du navigateur"""
        if self.is_running:
            logger.warning("Automatisation déjà en cours")
            return

        logger.info(f"🚀 DÉMARRAGE automatisation pour {platform_profile.get('name', 'Unknown')}")

        # Configuration
        self.platform_profile = platform_profile
        self.browser_type = browser_type or "chrome"
        self.test_text = (automation_params or {}).get('test_text', 'Test automatisé')
        self.skip_browser_activation = (automation_params or {}).get('skip_browser_activation', False)
        self.extracted_response = ""

        # État
        self.is_running = True
        self.force_stop = False
        self.start_time = time.time()

        # EXÉCUTION DIRECTE
        try:
            self._execute_automation_sequence()
        except Exception as e:
            self._handle_automation_failure(f"Erreur séquence: {str(e)}")

    def _execute_automation_sequence(self):
        """Exécute toute la séquence d'automatisation"""
        logger.info("📋 Début séquence automatisation")

        try:
            # ÉTAPE 1: Focus navigateur PAR CLIC (pas Alt+Tab!)
            if not self._ensure_browser_focus():
                return

            # ÉTAPE 2: Cliquer champ
            if not self._handle_field_click_step():
                return

            # ÉTAPE 3: Effacer champ
            if not self._handle_field_clear_step():
                return

            # ÉTAPE 4: Saisir texte
            if not self._handle_text_input_step():
                return

            # ÉTAPE 5: Soumettre
            if not self._handle_form_submit_step():
                return

            # ÉTAPE 6: Attendre réponse IA
            if not self._handle_response_wait_step():
                return

            # ÉTAPE 7: Extraire réponse
            if not self._handle_response_extract_step():
                return

            # SUCCÈS FINAL
            self._handle_automation_success()

        except Exception as e:
            self._handle_automation_failure(f"Erreur dans séquence: {str(e)}")

    def _ensure_browser_focus(self):
        """ÉTAPE 1: S'assurer que le navigateur a le focus PAR CLIC"""
        if self.force_stop:
            return False

        logger.info("🌐 ÉTAPE 1: Focus navigateur par clic")
        self.step_completed.emit("browser_focusing", "Focus navigateur")

        try:
            # Si skip demandé, on suppose que le conductor a déjà géré
            if self.skip_browser_activation:
                logger.info("🔄 Skip focus - Conductor a déjà géré")
                time.sleep(0.5)
                return True

            # MÉTHODE CORRECTE: Cliquer dans la fenêtre du navigateur
            # On clique au centre de l'écran ou sur une zone neutre
            logger.info("🖱️ Clic pour focus navigateur")

            # Obtenir la taille de l'écran si possible
            try:
                import tkinter as tk
                root = tk.Tk()
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                root.destroy()

                # Cliquer au centre-haut de l'écran (zone généralement safe)
                click_x = screen_width // 2
                click_y = 100  # En haut mais pas trop (éviter la barre de titre)

            except:
                # Fallback: position par défaut
                click_x = 960
                click_y = 100

            # Clic pour focus
            self.mouse_controller.click(click_x, click_y)
            time.sleep(0.3)

            logger.info(f"✅ Clic de focus effectué à ({click_x}, {click_y})")

            # Si on a pygetwindow, vérifier qu'on a bien une fenêtre navigateur
            if HAS_PYGETWINDOW:
                try:
                    browser_keywords = {
                        'chrome': ['chrome', 'chromium'],
                        'firefox': ['firefox', 'mozilla'],
                        'edge': ['edge', 'microsoft edge'],
                        'safari': ['safari'],
                        'opera': ['opera'],
                        'brave': ['brave']
                    }

                    keywords = browser_keywords.get(self.browser_type.lower(), ['chrome', 'firefox', 'edge'])

                    all_windows = gw.getAllWindows()
                    browser_found = False

                    for window in all_windows:
                        window_title = window.title.lower()
                        if any(keyword in window_title for keyword in keywords):
                            browser_found = True
                            logger.info(f"✅ Fenêtre navigateur confirmée: {window.title}")
                            break

                    if not browser_found:
                        logger.warning("⚠️ Aucune fenêtre navigateur détectée, mais on continue")

                except Exception as e:
                    logger.debug(f"Vérification fenêtre: {e}")

            return True

        except Exception as e:
            logger.error(f"Erreur focus navigateur: {e}")
            # Continuer quand même
            return True

    def _handle_field_click_step(self):
        """ÉTAPE 2: Clic champ prompt"""
        if self.force_stop:
            return False

        logger.info("🎯 ÉTAPE 2: Clic champ prompt")
        self.step_completed.emit("field_clicking", "Clic sur champ")

        try:
            positions = self.platform_profile.get('interface_positions', {})
            prompt_pos = positions.get('prompt_field')

            if not prompt_pos:
                self._handle_automation_failure("Position champ prompt manquante")
                return False

            x, y = prompt_pos['center_x'], prompt_pos['center_y']
            logger.info(f"🎯 Position cible: ({x}, {y})")

            # Double clic pour s'assurer du focus
            self.mouse_controller.click(x, y)
            time.sleep(0.2)
            self.mouse_controller.click(x, y)
            time.sleep(0.3)

            logger.info("✅ Double clic effectué")
            return True

        except Exception as e:
            self._handle_automation_failure(f"Erreur clic champ: {str(e)}")
            return False

    def _handle_field_clear_step(self):
        """ÉTAPE 3: Effacer champ"""
        if self.force_stop:
            return False

        logger.info("🧹 ÉTAPE 3: Effacement champ")
        self.step_completed.emit("field_clearing", "Effacement champ")

        try:
            # Méthode 1: Triple clic pour tout sélectionner
            positions = self.platform_profile.get('interface_positions', {})
            prompt_pos = positions.get('prompt_field')

            if prompt_pos:
                x, y = prompt_pos['center_x'], prompt_pos['center_y']
                # Triple clic
                for _ in range(3):
                    self.mouse_controller.click(x, y)
                    time.sleep(0.1)
                time.sleep(0.2)
                # Supprimer
                self.keyboard_controller.press_key('delete')
                time.sleep(0.2)
                logger.info("✅ Effacement par triple clic")
            else:
                # Méthode 2: Ctrl+A puis Delete
                self.keyboard_controller.hotkey('ctrl', 'a')
                time.sleep(0.1)
                self.keyboard_controller.press_key('delete')
                time.sleep(0.2)
                logger.info("✅ Effacement par Ctrl+A")

            return True

        except Exception as e:
            self._handle_automation_failure(f"Erreur effacement: {str(e)}")
            return False

    def _handle_text_input_step(self):
        """ÉTAPE 4: Saisie texte"""
        if self.force_stop:
            return False

        logger.info("📝 ÉTAPE 4: Saisie texte")
        self.step_completed.emit("text_typing", "Saisie texte")

        try:
            if not self.test_text:
                self._handle_automation_failure("Texte de test manquant")
                return False

            logger.info(f"📝 Saisie: '{self.test_text}' ({len(self.test_text)} caractères)")

            # MÉTHODE 1: Presse-papiers (plus fiable)
            try:
                # Sauvegarder presse-papiers
                original_clipboard = pyperclip.paste()

                # Copier notre texte
                pyperclip.copy(self.test_text)
                time.sleep(0.1)

                # Coller
                self.keyboard_controller.hotkey('ctrl', 'v')
                time.sleep(0.5)

                # Restaurer presse-papiers
                pyperclip.copy(original_clipboard)

                logger.info("✅ Saisie par presse-papiers réussie")
                return True

            except Exception as e:
                logger.warning(f"Erreur presse-papiers: {e}, essai saisie directe...")

            # MÉTHODE 2: Saisie directe
            try:
                self.keyboard_controller.type_text(self.test_text)
                time.sleep(0.8)
                logger.info("✅ Saisie directe réussie")
                return True

            except Exception as e:
                logger.error(f"Erreur saisie directe: {e}")
                self._handle_automation_failure("Échec toutes méthodes de saisie")
                return False

        except Exception as e:
            self._handle_automation_failure(f"Erreur saisie texte: {str(e)}")
            return False

    def _handle_form_submit_step(self):
        """ÉTAPE 5: Soumission formulaire"""
        if self.force_stop:
            return False

        logger.info("📤 ÉTAPE 5: Soumission")
        self.step_completed.emit("form_submitting", "Soumission")

        try:
            # Soumission avec Entrée
            self.keyboard_controller.press_key('enter')
            time.sleep(1)

            logger.info("✅ Formulaire soumis")
            return True

        except Exception as e:
            self._handle_automation_failure(f"Erreur soumission: {str(e)}")
            return False

    def _handle_response_wait_step(self):
        """ÉTAPE 6: Attendre réponse IA"""
        if self.force_stop:
            return False

        logger.info("🔍 ÉTAPE 6: Attente réponse IA")
        self.step_completed.emit("response_waiting", "Attente réponse")

        try:
            platform_name = self.platform_profile.get('name', '')

            # Calcul intelligent du temps d'attente
            wait_time = self._calculate_intelligent_wait_time()
            logger.info(f"⏱️ Temps d'attente calculé: {wait_time}s")

            # Utiliser le MutationObserver du conductor si disponible
            if hasattr(self.conductor, '_wait_for_ai_generation_mutation_observer'):
                logger.info(f"🔍 Utilisation MutationObserver du Conductor (max {wait_time}s)")
                result = self.conductor._wait_for_ai_generation_mutation_observer(platform_name, wait_time)

                if result.get('detected'):
                    logger.info(f"✅ Réponse IA détectée en {result.get('duration', 0):.1f}s")
                    return True
                else:
                    logger.warning(f"⏰ Timeout MutationObserver après {wait_time}s - tentative extraction")
                    return True
            else:
                # Fallback délai calculé
                logger.warning(f"MutationObserver indisponible - délai fixe {wait_time}s")
                time.sleep(wait_time)
                return True

        except Exception as e:
            logger.warning(f"Erreur attente réponse: {str(e)} - continuation")
            return True

    def _calculate_intelligent_wait_time(self):
        """Calcule un temps d'attente intelligent basé sur la longueur du prompt"""
        try:
            if not self.test_text:
                return 8

            # Analyse du prompt
            char_count = len(self.test_text)
            word_count = len(self.test_text.split())

            # Formule : 0.1s par caractère + 0.3s par mot + base 3s
            base_time = 3
            char_factor = char_count * 0.1
            word_factor = word_count * 0.3

            calculated_time = base_time + char_factor + word_factor

            # Limites
            min_time = 5
            max_time = 25
            final_time = max(min_time, min(calculated_time, max_time))

            logger.info(
                f"📊 Calcul attente: {char_count} chars × 0.1s + {word_count} mots × 0.3s + 3s base = {final_time:.1f}s")

            return int(final_time)

        except Exception as e:
            logger.warning(f"Erreur calcul temps attente: {e}")
            return 10

    def _handle_response_extract_step(self):
        """ÉTAPE 7: Extraction réponse avec console correcte"""
        if self.force_stop:
            return False

        logger.info("📄 ÉTAPE 7: Extraction réponse")
        self.step_completed.emit("response_extracting", "Extraction")

        try:
            platform_name = self.platform_profile.get('name', '')

            # Récupérer config d'extraction depuis le profil
            detection_config = self.platform_profile.get('detection_config', {})

            # Sélecteurs à tester
            selectors = []
            if detection_config.get('primary_selector'):
                selectors.append(detection_config['primary_selector'])
            if detection_config.get('fallback_selectors'):
                selectors.extend(detection_config['fallback_selectors'])

            # Sélecteurs génériques fallback
            selectors.extend([
                '[data-message-author-role="assistant"]:last-child',
                '.message:last-child',
                '.ai-response:last-child',
                '[role="assistant"]:last-child',
                '.markdown:last-child',
                'p:last-child'
            ])

            logger.info(f"🎯 EXTRACTION avec sélecteurs: {selectors[:3]}...")

            # JavaScript d'extraction
            js_code = f'''
            (function() {{
                let selectors = {json.dumps(selectors[:5])};
                console.log("🔧 StateAutomation extraction avec sélecteurs:", selectors);

                for (let selector of selectors) {{
                    try {{
                        let elements = document.querySelectorAll(selector);
                        console.log("🔍 Sélecteur", selector, "->", elements.length, "éléments");

                        if (elements.length > 0) {{
                            let element = elements[elements.length - 1];
                            let text = (element.textContent || element.innerText || '').trim();

                            console.log("📝 Texte trouvé:", text.length, "caractères");
                            console.log("📝 Aperçu:", text.substring(0, 100));

                            if (text.length > 10 && 
                                !text.toLowerCase().includes('send a message') &&
                                !text.toLowerCase().includes('écrivez votre message')) {{

                                console.log("✅ EXTRACTION StateAutomation RÉUSSIE avec:", selector);
                                copy(text);
                                return true;
                            }}
                        }}
                    }} catch(e) {{
                        console.log("⚠️ Erreur sélecteur", selector, ":", e.message);
                        continue;
                    }}
                }}

                console.log("❌ ÉCHEC extraction StateAutomation");
                copy("EXTRACTION_FAILED");
                return false;
            }})();
            '''

            if self._execute_js_with_proper_console(js_code):
                result = pyperclip.paste().strip()

                if result != "EXTRACTION_FAILED" and len(result) > 10:
                    self.extracted_response = result
                    logger.info(f"✅ Réponse extraite: {len(result)} caractères")
                    logger.info(f"📝 Aperçu: {result[:200]}..." if len(result) > 200 else f"📝 Texte: {result}")
                    return True

            # Si échec, essayer extraction basique
            logger.warning("Échec extraction spécialisée, tentative basique...")
            if self._extract_basic_response():
                return True

            self._handle_automation_failure("Aucune réponse extraite")
            return False

        except Exception as e:
            self._handle_automation_failure(f"Erreur extraction: {str(e)}")
            return False

    def _execute_js_with_proper_console(self, js_code):
        """Exécution JavaScript avec ouverture correcte de la console"""
        try:
            # S'assurer du focus sur le navigateur d'abord
            logger.info("🖱️ Clic pour s'assurer du focus avant console")

            # Cliquer au centre de la fenêtre
            try:
                import tkinter as tk
                root = tk.Tk()
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                root.destroy()
                click_x = screen_width // 2
                click_y = screen_height // 2
            except:
                click_x = 960
                click_y = 540

            self.mouse_controller.click(click_x, click_y)
            time.sleep(0.3)

            # Ouvrir console avec le bon raccourci selon le navigateur
            logger.info(f"📋 Ouverture console pour {self.browser_type}")
            success = open_console_for_browser(self.browser_type, self.keyboard_controller, force_focus=False)

            if not success:
                logger.warning("Échec ouverture console spécifique, utilisation F12")
                self.keyboard_controller.press_key('f12')
                time.sleep(0.5)

            # Nettoyer et exécuter
            pyperclip.copy("console.clear();")
            self.keyboard_controller.hotkey('ctrl', 'v')
            self.keyboard_controller.press_key('enter')
            time.sleep(0.1)

            pyperclip.copy(js_code)
            self.keyboard_controller.hotkey('ctrl', 'v')
            self.keyboard_controller.press_key('enter')
            time.sleep(0.5)

            # Fermer console
            close_console_for_browser(self.browser_type, self.keyboard_controller)
            time.sleep(0.2)

            return True

        except Exception as e:
            logger.error(f"Erreur JS: {e}")
            try:
                # Essayer de fermer la console en cas d'erreur
                self.keyboard_controller.press_key('f12')
            except:
                pass
            return False

    def _extract_basic_response(self):
        """Extraction basique de secours"""
        try:
            js_code = '''
            (function() {
                console.log("🔧 Extraction basique...");
                let elements = document.querySelectorAll('p, div, span');
                let longestText = '';

                for (let el of elements) {
                    let text = (el.textContent || '').trim();
                    if (text.length > longestText.length && text.length > 20) {
                        longestText = text;
                    }
                }

                console.log("📊 Plus long texte trouvé:", longestText.length, "caractères");

                if (longestText.length > 20) {
                    console.log("✅ Extraction basique réussie");
                    copy(longestText);
                    return true;
                }

                console.log("❌ Extraction basique échouée");
                copy("NO_CONTENT");
                return false;
            })();
            '''

            if self._execute_js_with_proper_console(js_code):
                result = pyperclip.paste().strip()
                if result != "NO_CONTENT" and len(result) > 20:
                    self.extracted_response = result
                    logger.info(f"✅ Extraction basique réussie: {len(result)} caractères")
                    return True

            return False

        except Exception as e:
            logger.debug(f"Erreur extraction basique: {e}")
            return False

    def _handle_automation_success(self):
        """Gestion succès final"""
        duration = time.time() - self.start_time
        logger.info(f"🎉 AUTOMATISATION RÉUSSIE en {duration:.1f}s")

        self.is_running = False
        self.automation_completed.emit(True, f"Test réussi en {duration:.1f}s", duration, self.extracted_response)

    def _handle_automation_failure(self, error_message):
        """Gestion échec"""
        duration = time.time() - self.start_time if self.start_time else 0
        logger.error(f"❌ AUTOMATISATION ÉCHOUÉE: {error_message}")

        self.is_running = False
        self.automation_failed.emit("automation_error", error_message)

    def stop_automation(self):
        """Arrêt"""
        logger.info("🛑 ARRÊT AUTOMATISATION")

        self.force_stop = True
        self.is_running = False

        # Nettoyer - fermer console si ouverte
        try:
            close_console_for_browser(self.browser_type, self.keyboard_controller)
        except:
            pass

        # Réinitialiser
        if hasattr(self.conductor, 'browser_already_active'):
            self.conductor.browser_already_active = False

        duration = time.time() - self.start_time if self.start_time else 0
        self.automation_completed.emit(False, "Arrêté par utilisateur", duration, "")

    def get_current_status(self):
        """Statut actuel"""
        duration = time.time() - self.start_time if self.start_time else 0
        return {
            'is_running': self.is_running,
            'duration': duration,
            'force_stop': self.force_stop,
            'platform': self.platform_profile.get('name', '') if self.platform_profile else '',
            'extracted_response_length': len(self.extracted_response)
        }

    def is_automation_running(self):
        """Vérifie si en cours"""
        return self.is_running and not self.force_stop