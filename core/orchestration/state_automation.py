#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
core/orchestration/state_automation.py - VERSION CORRIGÉE

Corrections principales:
- Simple clic au lieu de double clic
- Optimisation temps d'attente
- Focus par clic sans changement de fenêtre
- Gestion correcte console sans force_focus
"""

import time
import json
import pyperclip
from enum import Enum
from PyQt5.QtCore import QObject, pyqtSignal
from utils.logger import logger
from utils.exceptions import OrchestrationError

try:
    import pygetwindow as gw

    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False


class StateBasedAutomation(QObject):
    """Automatisation optimisée avec clic simple et temps rapides"""

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

        logger.info("StateBasedAutomation OPTIMISÉ initialisé")

    def start_test_automation(self, platform_profile, num_tabs, browser_type, url, automation_params=None):
        """Démarre l'automatisation optimisée"""
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
        """Exécute toute la séquence d'automatisation OPTIMISÉE"""
        logger.info("📋 Début séquence automatisation OPTIMISÉE")

        try:
            # ÉTAPE 1: Focus navigateur PAR CLIC
            if not self._ensure_browser_focus():
                return

            # ÉTAPE 2: Cliquer champ (SIMPLE CLIC)
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

            # ÉTAPE 6: Attendre réponse IA (OPTIMISÉ)
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
        """ÉTAPE 1: S'assurer que le navigateur a le focus PAR CLIC SIMPLE"""
        if self.force_stop:
            return False

        logger.info("🌐 ÉTAPE 1: Focus navigateur par clic simple")
        self.step_completed.emit("browser_focusing", "Focus navigateur")

        try:
            # Si skip demandé, on suppose que le conductor a déjà géré
            if self.skip_browser_activation:
                logger.info("🔄 Skip focus - Conductor a déjà géré")
                time.sleep(0.3)  # Plus rapide
                return True

            # MÉTHODE OPTIMISÉE: Clic simple au centre
            logger.info("🖱️ Clic simple pour focus navigateur")

            # Position par défaut optimisée
            try:
                import tkinter as tk
                root = tk.Tk()
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                root.destroy()

                # Zone centre sécurisée
                click_x = screen_width // 2
                click_y = 200  # Plus bas pour éviter les onglets
            except:
                click_x = 960
                click_y = 200

            # UN SEUL CLIC
            self.mouse_controller.click(click_x, click_y)
            time.sleep(0.2)  # Plus rapide

            logger.info(f"✅ Clic simple effectué à ({click_x}, {click_y})")
            return True

        except Exception as e:
            logger.error(f"Erreur focus navigateur: {e}")
            return True

    def _handle_field_click_step(self):
        """ÉTAPE 2: Clic champ prompt (SIMPLE CLIC)"""
        if self.force_stop:
            return False

        logger.info("🎯 ÉTAPE 2: Clic SIMPLE champ prompt")
        self.step_completed.emit("field_clicking", "Clic sur champ")

        try:
            positions = self.platform_profile.get('interface_positions', {})
            prompt_pos = positions.get('prompt_field')

            if not prompt_pos:
                self._handle_automation_failure("Position champ prompt manquante")
                return False

            x, y = prompt_pos['center_x'], prompt_pos['center_y']
            logger.info(f"🎯 Position cible: ({x}, {y})")

            # UN SEUL CLIC au lieu de double clic
            self.mouse_controller.click(x, y)
            time.sleep(0.2)  # Plus rapide

            logger.info("✅ Clic simple effectué")
            return True

        except Exception as e:
            self._handle_automation_failure(f"Erreur clic champ: {str(e)}")
            return False

    def _handle_field_clear_step(self):
        """ÉTAPE 3: Effacer champ OPTIMISÉ"""
        if self.force_stop:
            return False

        logger.info("🧹 ÉTAPE 3: Effacement champ OPTIMISÉ")
        self.step_completed.emit("field_clearing", "Effacement champ")

        try:
            # Méthode rapide: Ctrl+A puis Delete
            self.keyboard_controller.hotkey('ctrl', 'a')
            time.sleep(0.1)
            self.keyboard_controller.press_key('delete')
            time.sleep(0.1)

            logger.info("✅ Effacement rapide par Ctrl+A")
            return True

        except Exception as e:
            self._handle_automation_failure(f"Erreur effacement: {str(e)}")
            return False

    def _handle_text_input_step(self):
        """ÉTAPE 4: Saisie texte OPTIMISÉE"""
        if self.force_stop:
            return False

        logger.info("📝 ÉTAPE 4: Saisie texte OPTIMISÉE")
        self.step_completed.emit("text_typing", "Saisie texte")

        try:
            if not self.test_text:
                self._handle_automation_failure("Texte de test manquant")
                return False

            logger.info(f"📝 Saisie: '{self.test_text}' ({len(self.test_text)} caractères)")

            # Méthode presse-papiers optimisée
            try:
                # Sauvegarder presse-papiers
                original_clipboard = pyperclip.paste()

                # Copier et coller
                pyperclip.copy(self.test_text)
                time.sleep(0.05)  # Plus rapide
                self.keyboard_controller.hotkey('ctrl', 'v')
                time.sleep(0.3)  # Plus rapide

                # Restaurer presse-papiers
                pyperclip.copy(original_clipboard)

                logger.info("✅ Saisie rapide par presse-papiers")
                return True

            except Exception as e:
                logger.warning(f"Erreur presse-papiers: {e}, fallback saisie directe")
                self.keyboard_controller.type_text(self.test_text)
                time.sleep(0.5)
                return True

        except Exception as e:
            self._handle_automation_failure(f"Erreur saisie texte: {str(e)}")
            return False

    def _handle_form_submit_step(self):
        """ÉTAPE 5: Soumission formulaire RAPIDE"""
        if self.force_stop:
            return False

        logger.info("📤 ÉTAPE 5: Soumission RAPIDE")
        self.step_completed.emit("form_submitting", "Soumission")

        try:
            # Soumission avec Entrée
            self.keyboard_controller.press_key('enter')
            time.sleep(0.5)  # Plus rapide

            logger.info("✅ Formulaire soumis rapidement")
            return True

        except Exception as e:
            self._handle_automation_failure(f"Erreur soumission: {str(e)}")
            return False

    def _handle_response_wait_step(self):
        """ÉTAPE 6: Attendre réponse IA OPTIMISÉE"""
        if self.force_stop:
            return False

        logger.info("🔍 ÉTAPE 6: Attente réponse IA OPTIMISÉE")
        self.step_completed.emit("response_waiting", "Attente réponse")

        try:
            platform_name = self.platform_profile.get('name', '')

            # Calcul temps d'attente OPTIMISÉ
            wait_time = self._calculate_optimized_wait_time()
            logger.info(f"⏱️ Temps d'attente OPTIMISÉ: {wait_time}s")

            # Utiliser le MutationObserver SAFE du conductor
            if hasattr(self.conductor, '_wait_for_ai_generation_mutation_observer'):
                logger.info(f"🔍 Utilisation MutationObserver SAFE du Conductor (max {wait_time}s)")
                result = self.conductor._wait_for_ai_generation_mutation_observer(platform_name, wait_time)

                if result.get('detected'):
                    logger.info(f"✅ Réponse IA détectée RAPIDEMENT en {result.get('duration', 0):.1f}s")
                    return True
                else:
                    logger.info(f"⏰ Timeout MutationObserver après {wait_time}s - extraction immédiate")
                    return True
            else:
                # Fallback délai COURT
                logger.info(f"Fallback délai COURT {wait_time}s")
                time.sleep(wait_time)
                return True

        except Exception as e:
            logger.warning(f"Erreur attente réponse: {str(e)} - continuation")
            return True

    def _calculate_optimized_wait_time(self):
        """Calcule un temps d'attente OPTIMISÉ et plus court"""
        try:
            if not self.test_text:
                return 5  # Plus court

            # Analyse RAPIDE du prompt
            char_count = len(self.test_text)
            word_count = len(self.test_text.split())

            # Formule OPTIMISÉE : plus rapide
            base_time = 2  # Base réduite
            char_factor = char_count * 0.05  # Facteur réduit
            word_factor = word_count * 0.15  # Facteur réduit

            calculated_time = base_time + char_factor + word_factor

            # Limites RÉDUITES
            min_time = 3  # Minimum réduit
            max_time = 12  # Maximum réduit
            final_time = max(min_time, min(calculated_time, max_time))

            logger.info(
                f"📊 Calcul OPTIMISÉ: {char_count} chars × 0.05s + {word_count} mots × 0.15s + 2s base = {final_time:.1f}s")

            return int(final_time)

        except Exception as e:
            logger.warning(f"Erreur calcul temps attente: {e}")
            return 6  # Défaut plus court

    def _handle_response_extract_step(self):
        """ÉTAPE 7: Extraction réponse OPTIMISÉE"""
        if self.force_stop:
            return False

        logger.info("📄 ÉTAPE 7: Extraction réponse OPTIMISÉE")
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

            logger.info(f"🎯 EXTRACTION OPTIMISÉE avec sélecteurs: {selectors[:3]}...")

            # JavaScript d'extraction OPTIMISÉ
            js_code = f'''
            (function() {{
                let selectors = {json.dumps(selectors[:5])};
                console.log("🔧 StateAutomation extraction OPTIMISÉE:", selectors);

                for (let selector of selectors) {{
                    try {{
                        let elements = document.querySelectorAll(selector);
                        console.log("🔍 Sélecteur", selector, "->", elements.length, "éléments");

                        if (elements.length > 0) {{
                            let element = elements[elements.length - 1];
                            let text = (element.textContent || element.innerText || '').trim();

                            console.log("📝 Texte trouvé:", text.length, "caractères");

                            if (text.length > 10 && 
                                !text.toLowerCase().includes('send a message') &&
                                !text.toLowerCase().includes('écrivez votre message')) {{

                                console.log("✅ EXTRACTION OPTIMISÉE RÉUSSIE avec:", selector);
                                copy(text);
                                return true;
                            }}
                        }}
                    }} catch(e) {{
                        console.log("⚠️ Erreur sélecteur", selector, ":", e.message);
                        continue;
                    }}
                }}

                console.log("❌ ÉCHEC extraction optimisée");
                copy("EXTRACTION_FAILED");
                return false;
            }})();
            '''

            if self._execute_js_optimized(js_code):
                result = pyperclip.paste().strip()

                if result != "EXTRACTION_FAILED" and len(result) > 10:
                    self.extracted_response = result
                    logger.info(f"✅ Réponse extraite RAPIDEMENT: {len(result)} caractères")
                    logger.info(f"📝 Aperçu: {result[:150]}..." if len(result) > 150 else f"📝 Texte: {result}")
                    return True

            # Fallback extraction basique RAPIDE
            logger.info("Échec extraction spécialisée, tentative basique RAPIDE...")
            if self._extract_basic_response_fast():
                return True

            self._handle_automation_failure("Aucune réponse extraite")
            return False

        except Exception as e:
            self._handle_automation_failure(f"Erreur extraction: {str(e)}")
            return False

    def _execute_js_optimized(self, js_code):
        """Exécution JavaScript OPTIMISÉE sans changement de fenêtre"""
        try:
            # Focus minimal sans changement de fenêtre
            logger.info("🖱️ Focus minimal avant console")

            # Clic centre simple
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
            time.sleep(0.2)  # Plus rapide

            # Ouvrir console RAPIDE selon navigateur
            logger.info(f"📋 Ouverture console RAPIDE pour {self.browser_type}")

            try:
                from config.console_shortcuts import open_console_for_browser
                # SANS force_focus pour éviter l'erreur
                success = open_console_for_browser(self.browser_type, self.keyboard_controller)
            except Exception as e:
                logger.info(f"Fallback raccourci direct: {e}")
                # Fallback direct
                if self.browser_type == 'firefox':
                    self.keyboard_controller.hotkey('ctrl', 'shift', 'k')
                else:
                    self.keyboard_controller.hotkey('ctrl', 'shift', 'j')
                time.sleep(0.5)
                success = True

            if not success:
                self.keyboard_controller.press_key('f12')
                time.sleep(0.4)

            # Nettoyer et exécuter RAPIDE
            pyperclip.copy("console.clear();")
            self.keyboard_controller.hotkey('ctrl', 'v')
            self.keyboard_controller.press_key('enter')
            time.sleep(0.1)

            pyperclip.copy(js_code)
            self.keyboard_controller.hotkey('ctrl', 'v')
            self.keyboard_controller.press_key('enter')
            time.sleep(0.3)  # Plus rapide

            # Fermer console RAPIDE
            try:
                from config.console_shortcuts import close_console_for_browser
                close_console_for_browser(self.browser_type, self.keyboard_controller)
            except:
                self.keyboard_controller.press_key('f12')

            time.sleep(0.1)
            return True

        except Exception as e:
            logger.error(f"Erreur JS optimisé: {e}")
            try:
                self.keyboard_controller.press_key('f12')
            except:
                pass
            return False

    def _extract_basic_response_fast(self):
        """Extraction basique RAPIDE de secours"""
        try:
            js_code = '''
            (function() {
                console.log("🔧 Extraction basique RAPIDE...");
                let elements = document.querySelectorAll('p, div, span');
                let longestText = '';

                for (let el of elements) {
                    let text = (el.textContent || '').trim();
                    if (text.length > longestText.length && text.length > 15) {  // Seuil plus bas
                        longestText = text;
                    }
                }

                if (longestText.length > 15) {  // Seuil plus bas
                    console.log("✅ Extraction basique RAPIDE réussie");
                    copy(longestText);
                    return true;
                }

                copy("NO_CONTENT");
                return false;
            })();
            '''

            if self._execute_js_optimized(js_code):
                result = pyperclip.paste().strip()
                if result != "NO_CONTENT" and len(result) > 15:
                    self.extracted_response = result
                    logger.info(f"✅ Extraction basique RAPIDE réussie: {len(result)} caractères")
                    return True

            return False

        except Exception as e:
            logger.debug(f"Erreur extraction basique rapide: {e}")
            return False

    def _handle_automation_success(self):
        """Gestion succès final"""
        duration = time.time() - self.start_time
        logger.info(f"🎉 AUTOMATISATION OPTIMISÉE RÉUSSIE en {duration:.1f}s")

        self.is_running = False
        self.automation_completed.emit(True, f"Test réussi en {duration:.1f}s", duration, self.extracted_response)

    def _handle_automation_failure(self, error_message):
        """Gestion échec"""
        duration = time.time() - self.start_time if self.start_time else 0
        logger.error(f"❌ AUTOMATISATION ÉCHOUÉE: {error_message}")

        self.is_running = False
        self.automation_failed.emit("automation_error", error_message)

    def stop_automation(self):
        """Arrêt RAPIDE"""
        logger.info("🛑 ARRÊT AUTOMATISATION RAPIDE")

        self.force_stop = True
        self.is_running = False

        # Nettoyer console RAPIDE
        try:
            from config.console_shortcuts import close_console_for_browser
            close_console_for_browser(self.browser_type, self.keyboard_controller)
        except:
            try:
                self.keyboard_controller.press_key('f12')
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