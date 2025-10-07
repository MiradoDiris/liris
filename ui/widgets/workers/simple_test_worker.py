import os
import time
import pyperclip
import json
from datetime import datetime
from PyQt5.QtCore import Qt, pyqtSignal, QThread

from utils.logger import logger
from ui.localization.translator import tr
from utils.selector_generator import (
    UniversalSelectorGenerator,
)  # Assuming this exists and is importable


# Copy SimpleTestWorker from final_test_widget.py
class SimpleTestWorker(QThread):
    test_completed = pyqtSignal(bool, str, float, str)
    step_update = pyqtSignal(str, str)
    debug_info = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self, conductor, platform_profile, test_message, detected_browser_type
    ):
        super().__init__()
        self.conductor = conductor
        self.platform_profile = platform_profile
        self.test_message = test_message
        self.detected_browser_type = detected_browser_type
        self.should_stop = False
        self.current_step = ""
        self.step_start_time = 0

        # NOUVEAU : Initialiser le générateur universel
        self.selector_generator = UniversalSelectorGenerator()

    def debug_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        full_message = f"[{timestamp}] {self.current_step}: {message}"
        logger.info(full_message)
        self.debug_info.emit(full_message)

    def start_step(self, step_name):
        self.current_step = step_name
        self.step_start_time = time.time()
        self.debug_log(f"🚀 DÉBUT de l'étape")

    def end_step(self, success=True):
        duration = time.time() - self.step_start_time
        status = "✅ SUCCÈS" if success else "❌ ÉCHEC"
        self.debug_log(f"{status} - Durée: {duration:.2f}s")

    def stop_test(self):
        self.should_stop = True
        self.debug_log("🛑 ARRÊT DEMANDÉ")

    def _get_platform_submit_method(self):
        """
        Détermine la méthode d'envoi selon l'URL de la plateforme

        Returns:
            str: 'ctrl_enter' pour Gemini, 'enter' pour les autres
        """
        try:
            browser_config = self.platform_profile.get("browser", {})
            platform_url = browser_config.get("url", "").lower()

            # Détection Gemini par URL
            gemini_domains = [
                "aistudio.google.com",
                "gemini.google.com",
                "bard.google.com",  # Au cas où il y aurait encore des anciennes URLs
            ]

            if any(domain in platform_url for domain in gemini_domains):
                return "ctrl_enter"

            # Par défaut : Enter normal
            return "enter"

        except Exception as e:
            self.debug_log(f"⚠️ Erreur détection méthode envoi: {e}")
            return "enter"  # Fallback sécurisé

    def _execute_form_submit(self):
        """Exécute l'envoi du formulaire avec la bonne méthode"""
        try:
            submit_method = self._get_platform_submit_method()

            if submit_method == "ctrl_enter":
                self.debug_log("Envoi formulaire (Ctrl+Enter pour Gemini)")
                self.conductor.keyboard_controller.hotkey("ctrl", "enter")
            else:
                self.debug_log("Envoi formulaire (Enter)")
                self.conductor.keyboard_controller.press_key("enter")

            time.sleep(0.5)
            self.debug_log("Envoi formulaire réussi")
            return True

        except Exception as e:
            self.debug_log(f"❌ Erreur envoi: {e}")
            return False

    def run(self):
        try:
            start_time = time.time()
            self.debug_log("🎯 DÉBUT DU TEST COMPLET UNIVERSEL")

            # ÉTAPE 1: Validation configuration
            self.start_step("VALIDATION_CONFIG")

            window_position = self.platform_profile.get("window_position")
            prompt_field = self.platform_profile.get("interface_positions", {}).get(
                "prompt_field"
            )
            extraction_config = self.platform_profile.get("extraction_config", {})
            detection_config = self.platform_profile.get("detection_config", {})

            self.debug_log(f"window_position: {window_position}")
            self.debug_log(f"prompt_field: {prompt_field}")
            self.debug_log(f"extraction_config présent: {bool(extraction_config)}")
            self.debug_log(f"detection_config présent: {bool(detection_config)}")

            # 🎯 NOUVEAU : Vérification configuration universelle
            response_area = extraction_config.get("response_area", {})
            universal_config = response_area.get("universal_config")
            if universal_config:
                self.debug_log(
                    f"🎯 Configuration universelle détectée pour: {universal_config.get('platform', 'Unknown')}"
                )
            else:
                self.debug_log("📋 Configuration legacy détectée")

            if (
                not window_position
                or "x" not in window_position
                or "y" not in window_position
            ):
                self.debug_log("❌ window_position invalide!")
                self.test_completed.emit(
                    False, "Configuration incomplète: window_position invalide", 0, ""
                )
                # self.finished.emit()
                return

            if (
                not prompt_field
                or "center_x" not in prompt_field
                or "center_y" not in prompt_field
            ):
                self.debug_log("❌ prompt_field invalide!")
                self.test_completed.emit(
                    False, "Configuration incomplète: prompt_field invalide", 0, ""
                )
                # self.finished.emit()
                return

            self.end_step(True)

            if self.should_stop:
                self.debug_log("🛑 Arrêt demandé avant début des actions")
                return

            # ÉTAPE 2: Clic icône fenêtre
            self.start_step("BROWSER_FOCUS")
            self.step_update.emit("browser_focusing", "Clic icône fenêtre...")

            try:
                x, y = window_position["x"], window_position["y"]
                self.debug_log(f"Clic sur position: ({x}, {y})")
                self.conductor.mouse_controller.click(x, y)
                time.sleep(0.5)
                self.debug_log("Clic icône réussi")

                # Ouverture URL de la plateforme
                browser_config = self.platform_profile.get("browser", {})
                platform_url = browser_config.get("url", "")
                if platform_url:
                    self.debug_log(f"Ouverture URL plateforme: {platform_url}")
                    result = self.conductor.browser_manager.open_url(
                        platform_url, self.detected_browser_type, new_window=False
                    )
                    if result.get("success"):
                        time.sleep(4)  # Attendre chargement page
                        self.debug_log("URL ouverte avec succès")
                    else:
                        self.debug_log(
                            f"⚠️ Échec ouverture URL: {result.get('error', 'Erreur inconnue')}"
                        )
                else:
                    self.debug_log("⚠️ Aucune URL configurée")

                self.end_step(True)
            except Exception as e:
                self.debug_log(f"❌ Erreur clic icône: {e}")
                self.end_step(False)
                self.test_completed.emit(False, f"Erreur clic icône: {str(e)}", 0, "")
                # self.finished.emit()
                return

            if self.should_stop:
                self.debug_log("🛑 Arrêt demandé après clic icône")
                return

            # ÉTAPE 3: Clic champ de saisie
            self.start_step("FIELD_CLICK")
            self.step_update.emit("field_clicking", "Clic champ de saisie...")

            try:
                x, y = prompt_field["center_x"], prompt_field["center_y"]
                self.debug_log(f"Clic champ prompt: ({x}, {y})")
                self.conductor.mouse_controller.click(x, y)
                time.sleep(0.3)
                self.debug_log("Clic champ réussi")
                self.end_step(True)
            except Exception as e:
                self.debug_log(f"❌ Erreur clic champ: {e}")
                self.end_step(False)
                self.test_completed.emit(False, f"Erreur clic champ: {str(e)}", 0, "")
                # self.finished.emit()
                return

            if self.should_stop:
                self.debug_log("🛑 Arrêt demandé après clic champ")
                return

            # ÉTAPE 4: Nettoyage champ
            self.start_step("FIELD_CLEAR")
            self.step_update.emit("text_typing", "Nettoyage et saisie...")

            try:
                self.debug_log("Effacement champ (Ctrl+A + Delete)")
                self.conductor.keyboard_controller.hotkey("ctrl", "a")
                time.sleep(0.1)
                self.conductor.keyboard_controller.press_key("delete")
                time.sleep(0.1)
                self.debug_log("Nettoyage champ réussi")
                self.end_step(True)
            except Exception as e:
                self.debug_log(f"❌ Erreur nettoyage: {e}")
                self.end_step(False)
                self.test_completed.emit(False, f"Erreur nettoyage: {str(e)}", 0, "")
                # self.finished.emit()
                return

            # ÉTAPE 5: Saisie texte
            self.start_step("TEXT_INPUT")

            try:
                self.debug_log(
                    f"Saisie texte: '{self.test_message}' (longueur: {len(self.test_message)})"
                )

                try:
                    original_clipboard = pyperclip.paste()
                    pyperclip.copy(self.test_message)
                    time.sleep(0.05)
                    self.conductor.keyboard_controller.hotkey("ctrl", "v")
                    time.sleep(0.3)
                    pyperclip.copy(original_clipboard)
                    self.debug_log("Saisie via presse-papiers réussie")
                except Exception as e:
                    self.debug_log(f"Échec presse-papiers: {e}, fallback clavier")
                    self.conductor.keyboard_controller.type_text(self.test_message)
                    time.sleep(0.5)
                    self.debug_log("Saisie via clavier réussie")

                self.end_step(True)
            except Exception as e:
                self.debug_log(f"❌ Erreur saisie texte: {e}")
                self.end_step(False)
                self.test_completed.emit(False, f"Erreur saisie: {str(e)}", 0, "")
                # self.finished.emit()
                return

            if self.should_stop:
                self.debug_log("🛑 Arrêt demandé après saisie")
                return

            # ÉTAPE 6: Envoi formulaire (CORRIGÉ POUR GEMINI)
            self.start_step("FORM_SUBMIT")
            self.step_update.emit("form_submitting", "Envoi...")

            if not self._execute_form_submit():
                self.end_step(False)
                self.test_completed.emit(False, "Erreur envoi formulaire", 0, "")
                # self.finished.emit()
                return

            self.end_step(True)

            if self.should_stop:
                self.debug_log("🛑 Arrêt demandé après envoi")
                return

            # ÉTAPE 7: Attente réponse avec DÉTECTION UNIVERSELLE
            self.start_step("RESPONSE_WAIT")
            self.step_update.emit(
                "response_waiting", "Détection fin génération universelle..."
            )

            detection_success = False
            try:
                self.debug_log("🎯 Début détection IA universelle...")
                detection_success = self._wait_for_ai_completion(detection_config)
                self.debug_log(f"Résultat détection universelle: {detection_success}")
                self.end_step(detection_success)
            except Exception as e:
                self.debug_log(f"❌ Erreur détection universelle: {e}")
                self.end_step(False)
                logger.warning("Détection timeout - extraction forcée")

            if self.should_stop:
                self.debug_log("🛑 Arrêt demandé après détection")
                return

            if not detection_success:
                self.debug_log(
                    "⚠️ Détection a échoué, mais continuation vers extraction"
                )

            # ÉTAPE 8: Extraction réponse avec EXTRACTION UNIVERSELLE
            self.start_step("RESPONSE_EXTRACT")
            self.step_update.emit(
                "response_extracting",
                "Extraction console avec sélecteurs universels...",
            )

            response = ""
            try:
                self.debug_log("🎯 Début extraction universelle...")
                response = self._extract_response_universal(extraction_config)
                self.debug_log(
                    f"Extraction universelle terminée - Longueur: {len(response) if response else 0}"
                )

                if response:
                    self.debug_log(f"Aperçu réponse: '{response[:100]}...'")
                else:
                    self.debug_log("❌ Aucune réponse extraite")

                self.end_step(bool(response))
            except Exception as e:
                self.debug_log(f"❌ Erreur extraction universelle: {e}")
                response = ""
                self.end_step(False)

            # ÉTAPE 9: Finalisation
            duration = time.time() - start_time
            self.debug_log(f"🏁 TEST UNIVERSEL TERMINÉ - Durée totale: {duration:.2f}s")

            if response and len(response) > 10:
                self.debug_log(
                    f"✅ SUCCÈS UNIVERSEL - Réponse extraite: {len(response)} caractères"
                )
                self.test_completed.emit(
                    True,
                    f"Test universel réussi en {duration:.1f}s",
                    duration,
                    response,
                )
                # self.finished.emit()
            else:
                self.debug_log("❌ ÉCHEC UNIVERSEL - Aucune réponse valide extraite")
                self.test_completed.emit(False, "Aucune réponse extraite", duration, "")
                # self.finished.emit()

        except Exception as e:
            duration = time.time() - start_time if "start_time" in locals() else 0
            error_msg = f"Erreur étape {self.current_step}: {str(e)}"
            self.debug_log(f"💥 EXCEPTION UNIVERSELLE: {error_msg}")
            logger.error(error_msg, exc_info=True)
            self.test_completed.emit(False, error_msg, duration, "")
            # self.finished.emit()

    def _wait_for_ai_completion(self, detection_config):
        """VERSION AMÉLIORÉE avec générateur universel"""
        try:
            if not detection_config:
                self.debug_log("⚠️ Pas de config détection - attente fallback 8s")
                time.sleep(8)
                return True

            # 🎯 NOUVEAU : Utilisation du générateur universel pour les scripts
            universal_config = detection_config.get("universal_config")
            if universal_config:
                self.debug_log(
                    f"🎯 Utilisation détection universelle pour {universal_config['platform']}"
                )
                js_code = self.selector_generator.generate_detection_script(
                    universal_config
                )
                self.debug_log("📜 Script de détection universel généré")
            else:
                # Fallback vers les scripts spécialisés existants
                platform_type = detection_config.get("platform_type", "").lower()
                self.debug_log(f"🔄 Fallback scripts spécialisés pour {platform_type}")
                if "chatgpt" in platform_type:
                    js_code = self._get_chatgpt_detection_script()
                elif "gemini" in platform_type:
                    js_code = self._get_gemini_detection_script()
                elif "claude" in platform_type:
                    js_code = self._get_claude_detection_script()
                else:
                    primary_selector = detection_config.get("primary_selector", "div")
                    js_code = self._get_generic_detection_script(primary_selector)

            # Focus fenêtre avant détection
            window_position = self.platform_profile.get("window_position", {})
            if window_position:
                self.debug_log(
                    f"Focus fenêtre avant détection: ({window_position['x']}, {window_position['y']})"
                )
                self.conductor.mouse_controller.click(
                    window_position["x"], window_position["y"]
                )
                time.sleep(0.2)

            return self._execute_detection_script(js_code)

        except Exception as e:
            self.debug_log(f"❌ Erreur _wait_for_ai_completion: {e}")
            logger.error(f"Erreur détection IA: {e}")
            time.sleep(6)
            return False

    def _get_chatgpt_detection_script(self):
        """Ancienne méthode ChatGPT en fallback"""
        return """
        (function() {
            let lastDataState = '';
            let stableCount = 0;
            let checkCount = 0;
            let maxChecks = 1000;
            
            // Store result in global variable AND console log
            function setDetectionResult(result) {
                window.LIRIS_DETECTION_RESULT = result;
                console.log("LIRIS_DETECTION_COMPLETE:" + result);
                console.log("Detection result stored in window.LIRIS_DETECTION_RESULT");
            }
            
            function checkDataStability() {
                try {
                    checkCount++;
                    if (checkCount > maxChecks) {
                        setDetectionResult("timeout");
                        return;
                    }
                    
                    let elements = document.querySelectorAll('[data-start][data-end]');
                    let currentState = '';
                    elements.forEach(el => {
                        let start = el.getAttribute('data-start') || '';
                        let end = el.getAttribute('data-end') || '';
                        currentState += start + ':' + end + ';';
                    });
                    
                    if (currentState === lastDataState && currentState.length > 0) {
                        stableCount++;
                        if (stableCount >= 3) {
                            setDetectionResult("success");
                            return;
                        }
                    } else {
                        lastDataState = currentState;
                        stableCount = 0;
                    }
                    
                    setTimeout(checkDataStability, 300);
                } catch(e) {
                    setDetectionResult("error");
                }
            }
            
            // Initialize detection result
            window.LIRIS_DETECTION_RESULT = "running";
            checkDataStability();
            return "ChatGPT detection started";
        })();
        """

    def _get_gemini_detection_script(self):
        """Ancienne méthode Gemini en fallback"""
        return """
        (function() {
            let lastContentState = '';
            let stableCount = 0;
            let checkCount = 0;
            let maxChecks = 1000;
            
            function checkGeminiCompletion() {
                try {
                    checkCount++;
                    console.log("Gemini check #" + checkCount);
                    
                    if (checkCount > maxChecks) {
                        console.log("LIRIS_DETECTION_COMPLETE:timeout");
                        return;
                    }
                    
                    let generatingDiv = document.querySelector('[class*="_ngcontent-ng-c2459883256"]');
                    let completedDiv = document.querySelector('[class*="_ngcontent-ng-c1375136285"]');
                    
                    console.log("Generating div found:", !!generatingDiv);
                    console.log("Completed div found:", !!completedDiv);
                    
                    let currentState = (generatingDiv ? 'generating' : '') + (completedDiv ? 'completed' : '');
                    
                    if (currentState === lastContentState && completedDiv) {
                        stableCount++;
                        console.log("Stable count:", stableCount);
                        if (stableCount >= 2) {
                            console.log("LIRIS_DETECTION_COMPLETE:success");
                            return;
                        }
                    } else {
                        lastContentState = currentState;
                        stableCount = 0;
                    }
                    
                    setTimeout(checkGeminiCompletion, 400);
                } catch(e) {
                    console.log("Error in Gemini detection:", e);
                    console.log("LIRIS_DETECTION_COMPLETE:error");
                }
            }

            checkGeminiCompletion();
            return "Gemini detection started";
        })();
        """

    def _get_claude_detection_script(self):
        """Ancienne méthode Claude en fallback"""
        return """
        (function() {
            let checkCount = 0;
            let maxChecks = 1000;
        
            // Store result in global variable AND console log
            function setDetectionResult(result) {
                window.LIRIS_DETECTION_RESULT = result;
                console.log("LIRIS_DETECTION_COMPLETE:" + result);
                console.log("Detection result stored in window.LIRIS_DETECTION_RESULT");
            }
        
            function checkClaudeCompletion() {
                try {
                    checkCount++;
                    if (checkCount > maxChecks) {
                        setDetectionResult("timeout");
                        return;
                    }
                
                    let streamingElements = document.querySelectorAll('[data-is-streaming="true"]');
                    let completedElements = document.querySelectorAll('[data-is-streaming="false"]');
                
                    if (streamingElements.length === 0 && completedElements.length > 0) {
                        setDetectionResult("success");
                        return;
                    }
                
                    setTimeout(checkClaudeCompletion, 300);
                } catch(e) {
                    setDetectionResult("error");
                }
            }
        
            // Initialize detection result
            window.LIRIS_DETECTION_RESULT = "running";
            checkClaudeCompletion();
            return "Claude detection started";
        })();
        """

    def _get_generic_detection_script(self, selector):
        """Ancienne méthode générique en fallback"""
        return f'''
        (function() {{
            let lastText = '';
            let stableCount = 0;
            let checkCount = 0;
            let maxChecks = 1000;
            
            function checkTextStability() {{
                try {{
                    checkCount++;
                    console.log("Generic check #" + checkCount + " with selector: {selector}");
                    
                    if (checkCount > maxChecks) {{
                        console.log("LIRIS_DETECTION_COMPLETE:timeout");
                        return;
                    }}
                    
                    let element = document.querySelector("{selector}");
                    console.log("Element found:", !!element);
                    
                    let currentText = element ? (element.textContent || '').trim() : '';
                    console.log("Current text length:", currentText.length);
                    
                    if (currentText === lastText && currentText.length > 30) {{
                        stableCount++;
                        console.log("Stable count:", stableCount);
                        if (stableCount >= 3) {{
                            console.log("LIRIS_DETECTION_COMPLETE:success");
                            return;
                        }}
                    }} else {{
                        lastText = currentText;
                        stableCount = 0;
                    }}
                    
                    setTimeout(checkTextStability, 500);
                }} catch(e) {{
                    console.log("Error in generic detection:", e);
                    console.log("LIRIS_DETECTION_COMPLETE:error");
                }}
            }}

            checkTextStability();
            return "Generic detection started";
        }})();
        '''

    def _execute_detection_script(self, js_code):
        """Exécute le script de détection et surveille les résultats"""
        try:
            self.debug_log(f"🖥️ Ouverture console ({self.detected_browser_type})")

            if self.detected_browser_type == "firefox":
                self.conductor.keyboard_controller.hotkey("ctrl", "shift", "k")
            else:
                self.conductor.keyboard_controller.hotkey("ctrl", "shift", "j")
            time.sleep(0.5)

            if self.should_stop:
                self.debug_log("🛑 Arrêt pendant ouverture console")
                return False

            self.debug_log("🔐 Activation du collage")
            try:
                # Type 'allow pasting' to enable pasting in browser console
                self.conductor.keyboard_controller.type_text("allow pasting")
                self.conductor.keyboard_controller.press_key("enter")
                time.sleep(1)  # Wait for browser to process the allow pasting command
                self.debug_log("✅ Collage autorisé")
            except Exception as e:
                self.debug_log(f"⚠️ Erreur activation collage: {e}")

            self.debug_log("🧹 Nettoyage console")
            # pyperclip.copy("console.clear();")
            self.conductor.keyboard_controller.hotkey("ctrl", "v")
            self.conductor.keyboard_controller.press_key("enter")
            time.sleep(0.2)

            self.debug_log("💉 Injection script de détection")
            pyperclip.copy(js_code)
            self.conductor.keyboard_controller.hotkey("ctrl", "v")
            self.conductor.keyboard_controller.press_key("enter")
            time.sleep(0.5)

            max_wait = 80
            waited = 0
            check_interval = 0.5

            self.debug_log(
                f"👀 Surveillance console (max {max_wait}s, check chaque {check_interval}s)"
            )

            while waited < max_wait and not self.should_stop:
                try:
                    # Check the global variable instead of parsing console output
                    check_script = (
                        "console.log('STATUS_CHECK:' + window.LIRIS_DETECTION_RESULT);"
                    )

                    # Execute the status check script
                    pyperclip.copy(check_script)
                    self.conductor.keyboard_controller.hotkey("ctrl", "v")
                    self.conductor.keyboard_controller.press_key("enter")
                    time.sleep(0.2)

                    # Now we need to get the last console output
                    # Clear clipboard first
                    # pyperclip.copy("")

                    # Use a simple script to copy the detection result to clipboard
                    result_copy_script = """
                    if (window.LIRIS_DETECTION_RESULT) {
                        copy('RESULT:' + window.LIRIS_DETECTION_RESULT);
                    } else {
                        copy('RESULT:not_set');
                    }
                    """

                    pyperclip.copy(result_copy_script)
                    self.conductor.keyboard_controller.hotkey("ctrl", "v")
                    self.conductor.keyboard_controller.press_key("enter")
                    time.sleep(0.3)

                    # Get the result from clipboard
                    result_content = pyperclip.paste().strip()

                    self.debug_log(f"Detection result: {result_content}")

                    # Parse the result
                    if result_content.startswith("RESULT:"):
                        status = result_content.replace("RESULT:", "").strip()

                        if status == "success":
                            self.debug_log(f"✅ Détection réussie après {waited:.1f}s")
                            logger.info(f"✅ Détection réussie après {waited:.1f}s")
                            return True
                        elif status == "running":
                            continue
                        elif status == "timeout":
                            self.debug_log(f"⏱️ Détection timeout après {waited:.1f}s")
                            logger.warning(f"⏱️ Détection timeout après {waited:.1f}s")
                            return False
                        else:
                            self.debug_log(f"❌ Détection erreur: {status}")
                            logger.error(f"❌ Détection erreur: {status}")
                            return False

                except Exception as e:
                    self.debug_log(f"❌ Erreur vérification statut: {e}")

                time.sleep(check_interval)
                waited += check_interval

                if waited % 2 == 0:
                    self.debug_log(f"⏳ Attente détection... {waited:.1f}s/{max_wait}s")

            # self.conductor.keyboard_controller.press_key('f12')
            self.debug_log(f"⏱️ Timeout global détection après {waited:.1f}s")
            logger.warning(f"⏱️ Timeout global détection après {waited:.1f}s")
            return False

        except Exception as e:
            self.debug_log(f"❌ Erreur exécution détection: {e}")
            logger.error(f"❌ Erreur exécution détection: {e}")
            # try:
            #     self.conductor.keyboard_controller.press_key('f12')
            # except:
            #     pass
            return False

    def _extract_response_universal(self, extraction_config):
        """VERSION UNIVERSELLE avec sélecteurs automatiques"""
        try:
            self.debug_log("🎯 Début extraction réponse universelle")

            response_area = extraction_config.get("response_area", {})

            # 🆕 NOUVEAU : Utiliser la configuration universelle si disponible
            universal_config = response_area.get("universal_config")
            if universal_config:
                self.debug_log("🎯 Utilisation extraction universelle")
                extraction_selectors = universal_config["extraction"]
                primary_selector = extraction_selectors["primary_selector"]
                fallback_selectors = extraction_selectors.get("fallback_selectors", [])
                cleaning_method = extraction_selectors.get(
                    "text_cleaning", "basic_text_extraction"
                )
                platform = universal_config.get("platform", "unknown")

                self.debug_log(f"🎯 Plateforme: {platform}")
                self.debug_log(f"🧹 Méthode nettoyage: {cleaning_method}")
            else:
                # Fallback vers l'ancienne méthode
                self.debug_log("🔄 Fallback extraction classique")
                platform_config = response_area.get("platform_config", {})
                primary_selector = platform_config.get(
                    "primary_selector", "p:last-child"
                )
                fallback_selectors = platform_config.get("fallback_selectors", [])
                cleaning_method = "basic_text_extraction"
                platform = "legacy"

            self.debug_log(f"Primary selector: {primary_selector}")
            self.debug_log(f"Fallback selectors: {fallback_selectors}")

            # Focus fenêtre avant extraction
            window_position = self.platform_profile.get("window_position", {})
            if window_position:
                self.debug_log(
                    f"Focus fenêtre avant extraction: ({window_position['x']}, {window_position['y']})"
                )
                self.conductor.mouse_controller.click(
                    window_position["x"], window_position["y"]
                )
                time.sleep(0.2)

            selectors = [primary_selector] + fallback_selectors[:3]
            self.debug_log(f"Sélecteurs à tester: {selectors}")

            # 🎯 Script d'extraction universel optimisé
            js_code = f"""
            let selectors = {json.dumps(selectors)};
            let cleaningMethod = "basic_text_extraction";
            let platform = "legacy";

            // Define classes to be excluded from text content
            const excludedClasses = ["pt-3", "pb-3"]; // Add any other classes you want to exclude

            console.log("🎯 Testing universal selectors for " + platform + ":", selectors);
            console.log("🧹 Cleaning method:", cleaningMethod);
            console.log("🚫 Excluded classes:", excludedClasses);

            for (let i = 0; i < selectors.length; i++) {{
                let selector = selectors[i];
                console.log("Testing selector " + (i + 1) + ":", selector);

                try {{
                    let elements = document.querySelectorAll(selector);
                    console.log("Found " + elements.length + " elements for selector:", selector);

                    if (elements.length > 0) {{
                        // Get the last element (the most recent)
                        let element = elements[elements.length - 1];

                        // Create a deep clone of the element to avoid modifying the live DOM
                        let clonedElement = element.cloneNode(true);

                        // Replace elements with excluded classes with a newline character in the cloned element
                        excludedClasses.forEach(className => {{
                            const elementsToExclude = clonedElement.querySelectorAll(`.${{className}}`);
                            elementsToExclude.forEach(el => {{
                                // Create a text node with a newline
                                const newlineTextNode = document.createTextNode('\\n');
                                // Replace the excluded element with the newline text node
                                el.replaceWith(newlineTextNode);
                            }});
                        }});

                        let text = (clonedElement.textContent || '').trim();

                        // Clean the text based on the universal method
                        if (cleaningMethod === 'remove_ui_elements') {{
                            // Claude cleaning
                            text = text.replace(/Send a message\.\.\..*$/gi, '');
                            text = text.replace(/Stop generating.*$/gi, '');
                            text = text.replace(/Regenerate.*$/gi, '');
                        }} else if (cleaningMethod === 'preserve_markdown_structure') {{
                            // ChatGPT cleaning
                            text = text.replace(/Copy code.*$/gi, '');
                            text = text.replace(/Send a message.*$/gi, '');
                            text = text.replace(/Stop generating.*$/gi, '');
                        }} else if (cleaningMethod === 'extract_from_nested_spans') {{
                            // Gemini cleaning
                            text = text.replace(/Send a message.*$/gi, '');
                            text = text.replace(/Écrivez votre message.*$/gi, '');
                        }}

                        // Common cleaning
                        text = text.replace(/function\\(\\)\\s*\\{{.*\\}}/gi, '');
                        text = text.replace(/console\\.log.*$/gi, '');
                        text = text.replace(/let selectors.*$/gi, '');
                        text = text.replace(/Testing selector.*$/gi, '');
                        text = text.replace(/document\\.querySelector.*$/gi, '');
                        text = text.trim();

                        console.log("Cleaned text length:", text.length);
                        console.log("Text preview:", text.substring(0, 100));

                        if (!text.includes('console.log') &&
                            !text.includes('function()') &&
                            !text.includes('Testing selector') &&
                            !text.includes('document.querySelector') &&
                            !text.includes('Found ') &&
                            !text.includes('elements for selector')) {{
                            console.log("✅ Valid universal extraction found for " + platform + ", copying...");
                            copy(text);
                            break;
                        }} else {{
                            console.log("❌ Text rejected (contains debug info)");
                        }}
                    }}
                }} catch (e) {{
                    console.log("❌ Error with selector " + selector + ":", e);
                    continue;
                }}
            }}
            console.log("🎯 Universal extraction script completed for " + platform);
            """
            return self._execute_extraction_script(js_code)
        except Exception as e:
            self.debug_log(f"❌ Erreur extraction universelle: {e}")
            logger.error(f"Erreur extraction: {e}")
            # Fallback vers l'ancienne méthode
            return self._extract_response_simple_fallback(extraction_config)

    def _execute_extraction_script(self, js_code):
        """Exécute le script d'extraction universel et retourne le résultat"""
        try:
            self.debug_log("🖥️ Ouverture console pour extraction universelle")
            # In a real scenario, this would involve keyboard shortcuts to open dev tools
            # self.conductor.keyboard_controller.press_key('f12')
            # if self.detected_browser_type == 'firefox':
            # self.conductor.keyboard_controller.hotkey('ctrl', 'shift', 'k')
            # else:
            # self.conductor.keyboard_controller.hotkey('ctrl', 'shift', 'j')
            # time.sleep(0.5)
            if self.should_stop:
                self.debug_log("🛑 Arrêt pendant ouverture console extraction")
                return ""
            self.debug_log("🧹 Nettoyage console pour extraction")
            pyperclip.copy("console.clear();")
            self.conductor.keyboard_controller.hotkey("ctrl", "v")
            self.conductor.keyboard_controller.press_key("enter")
            time.sleep(0.1)
            self.debug_log("💉 Injection script d'extraction universel")
            pyperclip.copy(js_code)
            self.conductor.keyboard_controller.hotkey("ctrl", "v")
            self.conductor.keyboard_controller.press_key("enter")
            time.sleep(0.8)
            self.debug_log("📋 Lecture résultat extraction universelle")
            result = pyperclip.paste().strip()
            self.debug_log(f"Résultat brut longueur: {len(result)}")
            if result:
                self.debug_log(f"Aperçu résultat: '{result[:100]}...'")
                # self.conductor.keyboard_controller.press_key('f12') # Close dev tools
                time.sleep(0.1)
                if result:  # Validation supplémentaire
                    excluded_keywords = [
                        "function()",
                        "console.log",
                        "document.query",
                        "let ",
                        "const ",
                        "Testing selector",
                        "Found ",
                        "elements for selector",
                        "Error with selector",
                        "Universal extraction",
                        "Cleaning method",
                    ]
                    has_excluded = any(
                        keyword in result.lower() for keyword in excluded_keywords
                    )
                    self.debug_log(f"Test exclusion keywords: {has_excluded}")
                    if not has_excluded:
                        self.debug_log(
                            f"✅ Réponse universelle valide extraite: {len(result)} caractères"
                        )
                        return result
                    else:
                        self.debug_log("❌ Réponse rejetée (contient du code/debug)")
                else:
                    self.debug_log("❌ Réponse vide")
            return ""
        except Exception as e:
            self.debug_log(f"❌ Erreur extraction universelle: {e}")
            try:
                # Attempt to close dev tools if an error occurs
                self.conductor.keyboard_controller.press_key("f12")
            except:
                pass
            return ""

    def _extract_response_simple_fallback(self, extraction_config):
        """Ancienne méthode d'extraction en fallback"""
        try:
            self.debug_log("🔄 Fallback vers extraction simple")
            response_area = extraction_config.get("response_area", {})
            platform_config = response_area.get("platform_config", {})
            primary_selector = platform_config.get("primary_selector", "p:last-child")
            fallback_selectors = platform_config.get("fallback_selectors", [])
            self.debug_log(f"Primary selector fallback: {primary_selector}")
            self.debug_log(f"Fallback selectors: {fallback_selectors}")

            # Focus fenêtre avant extraction
            window_position = self.platform_profile.get("window_position", {})
            if window_position:
                self.debug_log(
                    f"Focus fenêtre avant extraction: ({window_position['x']}, {window_position['y']})"
                )
                self.conductor.mouse_controller.click(
                    window_position["x"], window_position["y"]
                )
                time.sleep(0.2)

            selectors = [primary_selector] + fallback_selectors[:3]
            self.debug_log(f"Sélecteurs fallback à tester: {selectors}")

            # Script d'extraction simple
            js_code = f"""
            let selectors = {json.dumps(selectors)};
            // Define classes to be excluded from text content
            const excludedClasses = ["pt-3", "pb-3"]; // Add any other classes you want to exclude

            console.log("🔄 Testing fallback selectors:", selectors);
            console.log("🚫 Excluded classes:", excludedClasses); // Log the excluded classes

            for (let i = 0; i < selectors.length; i++) {{
                let selector = selectors[i];
                console.log("Testing selector " + (i + 1) + ":", selector);
                try {{
                    let elements = document.querySelectorAll(selector);
                    console.log("Found " + elements.length + " elements for selector:", selector);
                    if (elements.length > 0) {{
                        let element = elements[elements.length - 1];

                        // Create a deep clone of the element to avoid modifying the live DOM
                        let clonedElement = element.cloneNode(true);

                        // Remove elements with excluded classes from the cloned element
                        excludedClasses.forEach(className => {{
                            const elementsToExclude = clonedElement.querySelectorAll(`.${{className}}`);
                            elementsToExclude.forEach(el => el.remove());
                        }});

                        let text = (clonedElement.textContent || '').trim(); // Get text from the cloned element
                        
                        console.log("Text length:", text.length);
                        console.log("Text preview:", text.substring(0, 50));
                        if (text.length > 15 && !text.includes('console.log') && !text.includes('function()') && !text.includes('Testing selector')) {{
                            console.log("Valid fallback text found, copying...");
                            copy(text);
                            break;
                        }} else {{
                            console.log("Text rejected (too short or contains debug)");
                        }}
                    }}
                }} catch(e) {{
                    console.log("Error with selector " + selector + ":", e);
                    continue;
                }}
            }}
            console.log("Fallback extraction script completed");
            """
            return self._execute_extraction_script(js_code)
        except Exception as e:
            self.debug_log(f"❌ Erreur extraction fallback: {e}")
            return ""

