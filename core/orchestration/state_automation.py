#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
core/orchestration/state_automation.py - VERSION CORRIGÉE EXTRACTION

Corrections principales:
- Simple clic au lieu de double clic
- Optimisation temps d'attente
- Focus par clic sans changement de fenêtre
- Gestion correcte console sans force_focus
- 🎯 CORRECTION MAJEURE: Utilisation de extraction_config.response_area pour l'extraction
- 🔧 CORRECTION FIREFOX: Ctrl+Entrée et récupération résultat console
- 🎉 CORRECTION COPY: Utilisation copy() directe au lieu de text;
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
        """ÉTAPE 7: Extraction réponse OPTIMISÉE - VERSION CORRIGÉE COPY"""
        if self.force_stop:
            return False

        logger.info("📄 ÉTAPE 7: Extraction réponse OPTIMISÉE")
        self.step_completed.emit("response_extracting", "Extraction")

        try:
            platform_name = self.platform_profile.get('name', '')

            # 🎯 CORRECTION MAJEURE: Récupérer config d'EXTRACTION (pas détection)
            extraction_config = self._get_extraction_config_from_profile()
            detection_config = self.platform_profile.get('detection_config', {})

            # Sélecteurs à tester POUR L'EXTRACTION
            selectors = []

            # PRIORITÉ 1: Config extraction depuis response_area
            if extraction_config:
                # 🎯 CORRECTION : Forcer les bons sélecteurs pour ChatGPT
                if 'chatgpt' in platform_name.lower():
                    logger.info("🔧 CORRECTION : Application sélecteurs ChatGPT optimisés")
                    selectors.extend([
                        'article[data-testid*="conversation-turn"] .markdown.prose',  # 🎯 PARFAIT
                        'article[data-testid*="conversation-turn"] .markdown',
                        '[data-message-author-role="assistant"] .markdown.prose',
                        'article[data-testid*="conversation-turn"]:last-child .prose'
                    ])
                else:
                    # Autres plateformes : utiliser config normale
                    if extraction_config.get('primary_selector'):
                        selectors.append(extraction_config['primary_selector'])
                        logger.info(f"🎯 Sélecteur extraction principal: {extraction_config['primary_selector']}")

                    if extraction_config.get('fallback_selectors'):
                        selectors.extend(extraction_config['fallback_selectors'])
                        logger.info(f"🎯 Sélecteurs extraction fallback: {extraction_config['fallback_selectors']}")

            # PRIORITÉ 2: Fallback depuis detection_config (ancienne méthode)
            elif detection_config:
                logger.warning("⚠️ Pas de config extraction - utilisation detection_config en fallback")
                if detection_config.get('primary_selector'):
                    selectors.append(detection_config['primary_selector'])
                if detection_config.get('fallback_selectors'):
                    selectors.extend(detection_config['fallback_selectors'])

            # PRIORITÉ 3: Sélecteurs génériques basés sur la plateforme
            if 'chatgpt' in platform_name.lower():
                # 🎯 UTILISER LES SÉLECTEURS QUI FONCTIONNENT (testés manuellement)
                selectors.extend([
                    'article[data-testid*="conversation-turn"] .markdown.prose',  # 🎯 PARFAIT - testé
                    'article[data-testid*="conversation-turn"]:last-of-type',  # 🎯 TESTÉ - marche
                    'article[data-testid="conversation-turn-2"]',  # 🎯 TESTÉ - marche
                    'article[data-scroll-anchor="true"]',  # 🎯 TESTÉ - marche
                    'article[data-testid*="conversation-turn"]',  # 🎯 TESTÉ - marche
                    '[data-message-author-role="assistant"] .markdown.prose',
                    '[data-start][data-end]'  # Fallback final
                ])
            else:
                # Sélecteurs génériques pour autres plateformes
                selectors.extend([
                    '[data-message-author-role="assistant"]:last-child',
                    '.message:last-child',
                    '.ai-response:last-child',
                    '[role="assistant"]:last-child',
                    '.markdown:last-child',
                    'p:last-child'
                ])

            logger.info(f"🎯 EXTRACTION OPTIMISÉE avec sélecteurs: {selectors[:3]}...")

            # 🎉 JavaScript d'extraction COPY DIRECTE - VERSION CORRIGÉE
            js_code = f'''
                        // 🎯 EXTRACTION COPY DIRECTE - MÉTHODE QUI MARCHE
                        let selectors = {json.dumps(selectors[:5])};

                        console.log("🔧 Extraction ChatGPT avec copy() directe...");

                        for (let selector of selectors) {{
                            try {{
                                let elements = document.querySelectorAll(selector);
                                if (elements.length > 0) {{
                                    let text = (elements[elements.length - 1].textContent || '').trim();
                                    if (text.length > 15 && 
                                        !text.includes('console.log') && 
                                        !text.includes('function()') &&
                                        !text.includes('🎯') &&
                                        !text.includes('Échec')) {{
                                        console.log("✅ Texte trouvé avec:", selector);
                                        console.log("📏 Longueur:", text.length, "caractères");

                                        // 🎉 COPY DIRECTE dans presse-papiers
                                        copy(text);
                                        console.log("✅ LIRIS_COPY_SUCCESS");
                                        break; // Sortir dès qu'on a trouvé
                                    }}
                                }}
                            }} catch(e) {{ 
                                console.log("❌ Erreur avec sélecteur:", selector, e.message);
                                continue; 
                            }}
                        }}

                        console.log("🔧 Extraction terminée");
                        '''

            if self._execute_js_optimized(js_code):
                # Vérifier que l'extraction copy() a fonctionné
                if self.extracted_response and len(self.extracted_response) > 15:
                    logger.info(f"✅ Réponse extraite via COPY: {len(self.extracted_response)} caractères")
                    logger.info(f"📝 Aperçu: {self.extracted_response[:150]}..." if len(
                        self.extracted_response) > 150 else f"📝 Texte: {self.extracted_response}")
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

    def _get_extraction_config_from_profile(self):
        """🎯 NOUVELLE MÉTHODE: Récupère la config d'extraction depuis response_area"""
        try:
            # Chemin: platform_profile['extraction_config']['response_area']['platform_config']
            extraction_config = self.platform_profile.get('extraction_config', {})
            if not extraction_config:
                logger.debug("Pas de extraction_config dans le profil")
                return None

            response_area = extraction_config.get('response_area', {})
            if not response_area:
                logger.debug("Pas de response_area dans extraction_config")
                return None

            platform_config = response_area.get('platform_config', {})
            if not platform_config:
                logger.debug("Pas de platform_config dans response_area")
                return None

            logger.info("✅ Configuration extraction trouvée depuis response_area")
            logger.info(f"   Sélecteur principal: {platform_config.get('primary_selector', 'N/A')}")
            logger.info(f"   Méthode: {platform_config.get('extraction_method', 'N/A')}")

            return platform_config

        except Exception as e:
            logger.error(f"Erreur récupération config extraction: {e}")
            return None

    def _execute_js_optimized(self, js_code):
        """Exécution JavaScript OPTIMISÉE avec copy() directe"""
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

            # 🎯 CORRECTION : Ctrl+Entrée pour Firefox
            if self.browser_type == 'firefox':
                self.keyboard_controller.hotkey('ctrl', 'enter')
            else:
                self.keyboard_controller.press_key('enter')
            time.sleep(0.1)

            pyperclip.copy(js_code)
            self.keyboard_controller.hotkey('ctrl', 'v')

            # 🎯 CORRECTION : Ctrl+Entrée pour Firefox
            if self.browser_type == 'firefox':
                self.keyboard_controller.hotkey('ctrl', 'enter')
            else:
                self.keyboard_controller.press_key('enter')
            time.sleep(0.5)  # Attendre exécution et copy()

            # 🎯 NOUVELLE MÉTHODE : RÉCUPÉRATION DIRECTE via copy()
            logger.info("🎯 Récupération directe via copy() - pas de parsing console")

            # Attendre que le copy() JavaScript soit effectué
            time.sleep(0.3)

            # Récupérer directement depuis le presse-papiers
            result = pyperclip.paste().strip()

            # Vérifier que c'est valide
            if result and len(result) > 15:
                # Vérification anti-JavaScript
                if not any(keyword in result.lower() for keyword in
                           ['function()', 'console.log', 'document.query', 'let ', 'const ', '🎯', 'console.clear']):
                    logger.info(f"✅ Extraction copy() réussie: {len(result)} caractères")
                    logger.info(f"📝 Aperçu: {result[:100]}..." if len(result) > 100 else f"📝 Texte: {result}")

                    # 🎉 STOCKER DANS extracted_response
                    self.extracted_response = result

                    # Fermer console RAPIDE
                    try:
                        from config.console_shortcuts import close_console_for_browser
                        close_console_for_browser(self.browser_type, self.keyboard_controller)
                    except:
                        self.keyboard_controller.press_key('f12')

                    time.sleep(0.1)
                    return True
                else:
                    logger.warning(f"⚠️ Contenu suspect détecté dans copy(): {result[:50]}...")
            else:
                logger.warning(f"⚠️ Copy() vide ou trop court: {len(result)} caractères")

            # Fermer console même en cas d'échec
            try:
                from config.console_shortcuts import close_console_for_browser
                close_console_for_browser(self.browser_type, self.keyboard_controller)
            except:
                self.keyboard_controller.press_key('f12')

            time.sleep(0.1)
            return False

        except Exception as e:
            logger.error(f"Erreur JS optimisé: {e}")
            try:
                self.keyboard_controller.press_key('f12')
            except:
                pass
            return False

    def _extract_basic_response_fast(self):
        """Extraction basique RAPIDE de secours avec COPY"""
        try:
            # 🎉 JavaScript COPY pour fallback
            js_code = '''
            // 🎯 MÉTHODE COPY DIRECTE pour ChatGPT - FALLBACK
            let chatgptSelectors = [
                'article[data-testid*="conversation-turn"] .markdown.prose',
                'article[data-testid*="conversation-turn"]:last-of-type', 
                'article[data-scroll-anchor="true"]',
                'article[data-testid*="conversation-turn"]'
            ];

            console.log("🔧 Extraction ChatGPT fallback avec copy()...");

            for (let selector of chatgptSelectors) {
                try {
                    let elements = document.querySelectorAll(selector);
                    if (elements.length > 0) {
                        let text = (elements[elements.length - 1].textContent || '').trim();
                        if (text.length > 15 && 
                            !text.includes('function()') && 
                            !text.includes('console.log') &&
                            !text.includes('🎯')) {
                            console.log("✅ Fallback trouvé avec:", selector);
                            console.log("📏 Longueur:", text.length, "caractères");

                            // 🎉 COPY DIRECTE dans presse-papiers
                            copy(text);
                            console.log("✅ LIRIS_FALLBACK_COPY_SUCCESS");
                            break; // Sortir dès qu'on a trouvé
                        }
                    }
                } catch(e) { 
                    console.log("❌ Erreur fallback:", selector, e.message);
                    continue; 
                }
            }

            console.log("🔧 Extraction fallback terminée");
            '''

            if self._execute_js_optimized(js_code):
                # Vérifier que le copy() fallback a fonctionné
                if self.extracted_response and len(self.extracted_response) > 15:
                    logger.info(f"✅ Extraction fallback COPY réussie: {len(self.extracted_response)} caractères")
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