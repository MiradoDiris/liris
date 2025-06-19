#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ui/widgets/tabs/final_test_widget.py
Version avec générateur universel intégré
"""

import time
import pyperclip
import json
import os
import re
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread

from utils.logger import logger
from utils.selector_generator import UniversalSelectorGenerator
from ui.styles.platform_config_style import PlatformConfigStyle


class SimpleTestWorker(QThread):
    test_completed = pyqtSignal(bool, str, float, str)
    step_update = pyqtSignal(str, str)
    debug_info = pyqtSignal(str)
    
    def __init__(self, conductor, platform_profile, test_message, detected_browser_type):
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
            browser_config = self.platform_profile.get('browser', {})
            platform_url = browser_config.get('url', '').lower()
            
            # Détection Gemini par URL
            gemini_domains = [
                'aistudio.google.com',
                'gemini.google.com',
                'bard.google.com'  # Au cas où il y aurait encore des anciennes URLs
            ]
            
            if any(domain in platform_url for domain in gemini_domains):
                return 'ctrl_enter'
            
            # Par défaut : Enter normal
            return 'enter'
            
        except Exception as e:
            self.debug_log(f"⚠️ Erreur détection méthode envoi: {e}")
            return 'enter'  # Fallback sécurisé
    
    def _execute_form_submit(self):
        """Exécute l'envoi du formulaire avec la bonne méthode"""
        try:
            submit_method = self._get_platform_submit_method()
            
            if submit_method == 'ctrl_enter':
                self.debug_log("Envoi formulaire (Ctrl+Enter pour Gemini)")
                self.conductor.keyboard_controller.hotkey('ctrl', 'enter')
            else:
                self.debug_log("Envoi formulaire (Enter)")
                self.conductor.keyboard_controller.press_key('enter')
            
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
            
            window_position = self.platform_profile.get('window_position')
            prompt_field = self.platform_profile.get('interface_positions', {}).get('prompt_field')
            extraction_config = self.platform_profile.get('extraction_config', {})
            detection_config = self.platform_profile.get('detection_config', {})
            
            self.debug_log(f"window_position: {window_position}")
            self.debug_log(f"prompt_field: {prompt_field}")
            self.debug_log(f"extraction_config présent: {bool(extraction_config)}")
            self.debug_log(f"detection_config présent: {bool(detection_config)}")
            
            # 🎯 NOUVEAU : Vérification configuration universelle
            response_area = extraction_config.get('response_area', {})
            universal_config = response_area.get('universal_config')
            if universal_config:
                self.debug_log(f"🎯 Configuration universelle détectée pour: {universal_config.get('platform', 'Unknown')}")
            else:
                self.debug_log("📋 Configuration legacy détectée")
            
            if not window_position or 'x' not in window_position or 'y' not in window_position:
                self.debug_log("❌ window_position invalide!")
                self.test_completed.emit(False, "Configuration incomplète: window_position invalide", 0, "")
                return
                
            if not prompt_field or 'center_x' not in prompt_field or 'center_y' not in prompt_field:
                self.debug_log("❌ prompt_field invalide!")
                self.test_completed.emit(False, "Configuration incomplète: prompt_field invalide", 0, "")
                return
            
            self.end_step(True)
            
            if self.should_stop:
                self.debug_log("🛑 Arrêt demandé avant début des actions")
                return
                
            # ÉTAPE 2: Clic icône fenêtre
            self.start_step("BROWSER_FOCUS")
            self.step_update.emit("browser_focusing", "Clic icône fenêtre...")
            
            try:
                x, y = window_position['x'], window_position['y']
                self.debug_log(f"Clic sur position: ({x}, {y})")
                self.conductor.mouse_controller.click(x, y)
                time.sleep(0.5)
                self.debug_log("Clic icône réussi")
                
                # Ouverture URL de la plateforme
                browser_config = self.platform_profile.get('browser', {})
                platform_url = browser_config.get('url', '')
                if platform_url:
                    self.debug_log(f"Ouverture URL plateforme: {platform_url}")
                    result = self.conductor.browser_manager.open_url(platform_url, self.detected_browser_type, new_window=False)
                    if result.get('success'):
                        time.sleep(2)  # Attendre chargement page
                        self.debug_log("URL ouverte avec succès")
                    else:
                        self.debug_log(f"⚠️ Échec ouverture URL: {result.get('error', 'Erreur inconnue')}")
                else:
                    self.debug_log("⚠️ Aucune URL configurée")
                
                self.end_step(True)
            except Exception as e:
                self.debug_log(f"❌ Erreur clic icône: {e}")
                self.end_step(False)
                self.test_completed.emit(False, f"Erreur clic icône: {str(e)}", 0, "")
                return
            
            if self.should_stop:
                self.debug_log("🛑 Arrêt demandé après clic icône")
                return
            
            # ÉTAPE 3: Clic champ de saisie
            self.start_step("FIELD_CLICK")
            self.step_update.emit("field_clicking", "Clic champ de saisie...")
            
            try:
                x, y = prompt_field['center_x'], prompt_field['center_y']
                self.debug_log(f"Clic champ prompt: ({x}, {y})")
                self.conductor.mouse_controller.click(x, y)
                time.sleep(0.3)
                self.debug_log("Clic champ réussi")
                self.end_step(True)
            except Exception as e:
                self.debug_log(f"❌ Erreur clic champ: {e}")
                self.end_step(False)
                self.test_completed.emit(False, f"Erreur clic champ: {str(e)}", 0, "")
                return
            
            if self.should_stop:
                self.debug_log("🛑 Arrêt demandé après clic champ")
                return
            
            # ÉTAPE 4: Nettoyage champ
            self.start_step("FIELD_CLEAR")
            self.step_update.emit("text_typing", "Nettoyage et saisie...")
            
            try:
                self.debug_log("Effacement champ (Ctrl+A + Delete)")
                self.conductor.keyboard_controller.hotkey('ctrl', 'a')
                time.sleep(0.1)
                self.conductor.keyboard_controller.press_key('delete')
                time.sleep(0.1)
                self.debug_log("Nettoyage champ réussi")
                self.end_step(True)
            except Exception as e:
                self.debug_log(f"❌ Erreur nettoyage: {e}")
                self.end_step(False)
                self.test_completed.emit(False, f"Erreur nettoyage: {str(e)}", 0, "")
                return
            
            # ÉTAPE 5: Saisie texte
            self.start_step("TEXT_INPUT")
            
            try:
                self.debug_log(f"Saisie texte: '{self.test_message}' (longueur: {len(self.test_message)})")
                
                try:
                    original_clipboard = pyperclip.paste()
                    pyperclip.copy(self.test_message)
                    time.sleep(0.05)
                    self.conductor.keyboard_controller.hotkey('ctrl', 'v')
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
                return
            
            self.end_step(True)
            
            if self.should_stop:
                self.debug_log("🛑 Arrêt demandé après envoi")
                return
            
            # ÉTAPE 7: Attente réponse avec DÉTECTION UNIVERSELLE
            self.start_step("RESPONSE_WAIT")
            self.step_update.emit("response_waiting", "Détection fin génération universelle...")
            
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
                self.debug_log("⚠️ Détection a échoué, mais continuation vers extraction")
            
            # ÉTAPE 8: Extraction réponse avec EXTRACTION UNIVERSELLE
            self.start_step("RESPONSE_EXTRACT")
            self.step_update.emit("response_extracting", "Extraction console avec sélecteurs universels...")
            
            response = ""
            try:
                self.debug_log("🎯 Début extraction universelle...")
                response = self._extract_response_universal(extraction_config)
                self.debug_log(f"Extraction universelle terminée - Longueur: {len(response) if response else 0}")
                
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
                self.debug_log(f"✅ SUCCÈS UNIVERSEL - Réponse extraite: {len(response)} caractères")
                self.test_completed.emit(True, f"Test universel réussi en {duration:.1f}s", duration, response)
            else:
                self.debug_log("❌ ÉCHEC UNIVERSEL - Aucune réponse valide extraite")
                self.test_completed.emit(False, "Aucune réponse extraite", duration, "")
                
        except Exception as e:
            duration = time.time() - start_time if 'start_time' in locals() else 0
            error_msg = f"Erreur étape {self.current_step}: {str(e)}"
            self.debug_log(f"💥 EXCEPTION UNIVERSELLE: {error_msg}")
            logger.error(error_msg, exc_info=True)
            self.test_completed.emit(False, error_msg, duration, "")
    
    def _wait_for_ai_completion(self, detection_config):
        """VERSION AMÉLIORÉE avec générateur universel"""
        try:
            if not detection_config:
                self.debug_log("⚠️ Pas de config détection - attente fallback 8s")
                time.sleep(8)
                return True
            
            # 🎯 NOUVEAU : Utilisation du générateur universel pour les scripts
            universal_config = detection_config.get('universal_config')
            if universal_config:
                self.debug_log(f"🎯 Utilisation détection universelle pour {universal_config['platform']}")
                js_code = self.selector_generator.generate_detection_script(universal_config)
                self.debug_log("📜 Script de détection universel généré")
            else:
                # Fallback vers les scripts spécialisés existants
                platform_type = detection_config.get('platform_type', '').lower()
                self.debug_log(f"🔄 Fallback scripts spécialisés pour {platform_type}")
                if 'chatgpt' in platform_type:
                    js_code = self._get_chatgpt_detection_script()
                elif 'gemini' in platform_type:
                    js_code = self._get_gemini_detection_script()
                elif 'claude' in platform_type:
                    js_code = self._get_claude_detection_script()
                else:
                    primary_selector = detection_config.get('primary_selector', 'div')
                    js_code = self._get_generic_detection_script(primary_selector)

            # Focus fenêtre avant détection
            window_position = self.platform_profile.get('window_position', {})
            if window_position:
                self.debug_log(f"Focus fenêtre avant détection: ({window_position['x']}, {window_position['y']})")
                self.conductor.mouse_controller.click(window_position['x'], window_position['y'])
                time.sleep(0.2)
            
            return self._execute_detection_script(js_code)
            
        except Exception as e:
            self.debug_log(f"❌ Erreur _wait_for_ai_completion: {e}")
            logger.error(f"Erreur détection IA: {e}")
            time.sleep(6)
            return False
    
    def _extract_response_universal(self, extraction_config):
        """VERSION UNIVERSELLE avec sélecteurs automatiques"""
        try:
            self.debug_log("🎯 Début extraction réponse universelle")
            
            response_area = extraction_config.get('response_area', {})
            
            # 🆕 NOUVEAU : Utiliser la configuration universelle si disponible
            universal_config = response_area.get('universal_config')
            if universal_config:
                self.debug_log("🎯 Utilisation extraction universelle")
                extraction_selectors = universal_config['extraction']
                primary_selector = extraction_selectors['primary_selector']
                fallback_selectors = extraction_selectors.get('fallback_selectors', [])
                cleaning_method = extraction_selectors.get('text_cleaning', 'basic_text_extraction')
                platform = universal_config.get('platform', 'unknown')
                
                self.debug_log(f"🎯 Plateforme: {platform}")
                self.debug_log(f"🧹 Méthode nettoyage: {cleaning_method}")
            else:
                # Fallback vers l'ancienne méthode
                self.debug_log("🔄 Fallback extraction classique")
                platform_config = response_area.get('platform_config', {})
                primary_selector = platform_config.get('primary_selector', 'p:last-child')
                fallback_selectors = platform_config.get('fallback_selectors', [])
                cleaning_method = 'basic_text_extraction'
                platform = 'legacy'

            self.debug_log(f"Primary selector: {primary_selector}")
            self.debug_log(f"Fallback selectors: {fallback_selectors}")
            
            # Focus fenêtre avant extraction
            window_position = self.platform_profile.get('window_position', {})
            if window_position:
                self.debug_log(f"Focus fenêtre avant extraction: ({window_position['x']}, {window_position['y']})")
                self.conductor.mouse_controller.click(window_position['x'], window_position['y'])
                time.sleep(0.2)
            
            selectors = [primary_selector] + fallback_selectors[:3]
            self.debug_log(f"Sélecteurs à tester: {selectors}")
            
            # 🎯 Script d'extraction universel optimisé
            js_code = f'''
            let selectors = {json.dumps(selectors)};
            let cleaningMethod = "{cleaning_method}";
            let platform = "{platform}";
            
            console.log("🎯 Testing universal selectors for " + platform + ":", selectors);
            console.log("🧹 Cleaning method:", cleaningMethod);
            
            for (let i = 0; i < selectors.length; i++) {{
                let selector = selectors[i];
                console.log("Testing selector " + (i+1) + ":", selector);
                
                try {{
                    let elements = document.querySelectorAll(selector);
                    console.log("Found " + elements.length + " elements for selector:", selector);
                    
                    if (elements.length > 0) {{
                        // Prendre le dernier élément (le plus récent)
                        let element = elements[elements.length - 1];
                        let text = (element.textContent || '').trim();
                        
                        // Nettoyer le texte selon la méthode universelle
                        if (cleaningMethod === 'remove_ui_elements') {{
                            // Nettoyage Claude
                            text = text.replace(/Send a message\\.\\.\\..*$/gi, '');
                            text = text.replace(/Stop generating.*$/gi, '');
                            text = text.replace(/Regenerate.*$/gi, '');
                        }} else if (cleaningMethod === 'preserve_markdown_structure') {{
                            // Nettoyage ChatGPT
                            text = text.replace(/Copy code.*$/gi, '');
                            text = text.replace(/Send a message.*$/gi, '');
                            text = text.replace(/Stop generating.*$/gi, '');
                        }} else if (cleaningMethod === 'extract_from_nested_spans') {{
                            // Nettoyage Gemini
                            text = text.replace(/Send a message.*$/gi, '');
                            text = text.replace(/Écrivez votre message.*$/gi, '');
                        }}
                        
                        // Nettoyage commun
                        text = text.replace(/function\\(\\)\\s*\\{{.*\\}}/gi, '');
                        text = text.replace(/console\\.log.*$/gi, '');
                        text = text.replace(/let selectors.*$/gi, '');
                        text = text.replace(/Testing selector.*$/gi, '');
                        text = text.replace(/document\\.querySelector.*$/gi, '');
                        text = text.trim();
                        
                        console.log("Cleaned text length:", text.length);
                        console.log("Text preview:", text.substring(0, 100));
                        
                        if (text.length > 20 && 
                            !text.includes('console.log') && 
                            !text.includes('function()') &&
                            !text.includes('Testing selector') &&
                            !text.includes('document.querySelector') &&
                            !text.includes('Found ') &&
                            !text.includes('elements for selector')) {{
                            console.log("✅ Valid universal extraction found for " + platform + ", copying...");
                            copy(text);
                            break;
                        }} else {{
                            console.log("❌ Text rejected (too short or contains debug info)");
                        }}
                    }}
                }} catch(e) {{ 
                    console.log("❌ Error with selector " + selector + ":", e);
                    continue; 
                }}
            }}
            console.log("🎯 Universal extraction script completed for " + platform);
            '''
            
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
            
            if self.detected_browser_type == 'firefox':
                self.conductor.keyboard_controller.hotkey('ctrl', 'shift', 'k')
            else:
                self.conductor.keyboard_controller.hotkey('ctrl', 'shift', 'j')
            time.sleep(0.5)
            
            if self.should_stop:
                self.debug_log("🛑 Arrêt pendant ouverture console extraction")
                return ""
            
            self.debug_log("🧹 Nettoyage console pour extraction")
            pyperclip.copy("console.clear();")
            self.conductor.keyboard_controller.hotkey('ctrl', 'v')
            self.conductor.keyboard_controller.press_key('enter')
            time.sleep(0.1)
            
            self.debug_log("💉 Injection script d'extraction universel")
            pyperclip.copy(js_code)
            self.conductor.keyboard_controller.hotkey('ctrl', 'v')
            self.conductor.keyboard_controller.press_key('enter')
            time.sleep(0.8)
            
            self.debug_log("📋 Lecture résultat extraction universelle")
            result = pyperclip.paste().strip()
            
            self.debug_log(f"Résultat brut longueur: {len(result)}")
            if result:
                self.debug_log(f"Aperçu résultat: '{result[:100]}...'")
            
            self.conductor.keyboard_controller.press_key('f12')
            time.sleep(0.1)
            
            if result and len(result) > 15:
                # Validation supplémentaire
                excluded_keywords = [
                    'function()', 'console.log', 'document.query', 'let ', 'const ', 
                    'Testing selector', 'Found ', 'elements for selector', 'Error with selector',
                    'Universal extraction', 'Cleaning method'
                ]
                has_excluded = any(keyword in result.lower() for keyword in excluded_keywords)
                
                self.debug_log(f"Test exclusion keywords: {has_excluded}")
                
                if not has_excluded:
                    self.debug_log(f"✅ Réponse universelle valide extraite: {len(result)} caractères")
                    return result
                else:
                    self.debug_log("❌ Réponse rejetée (contient du code/debug)")
            else:
                self.debug_log("❌ Réponse trop courte ou vide")
            
            return ""
            
        except Exception as e:
            self.debug_log(f"❌ Erreur extraction universelle: {e}")
            try:
                self.conductor.keyboard_controller.press_key('f12')
            except:
                pass
            return ""

    def _extract_response_simple_fallback(self, extraction_config):
        """Ancienne méthode d'extraction en fallback"""
        try:
            self.debug_log("🔄 Fallback vers extraction simple")
            
            response_area = extraction_config.get('response_area', {})
            platform_config = response_area.get('platform_config', {})
            primary_selector = platform_config.get('primary_selector', 'p:last-child')
            fallback_selectors = platform_config.get('fallback_selectors', [])

            self.debug_log(f"Primary selector fallback: {primary_selector}")
            self.debug_log(f"Fallback selectors: {fallback_selectors}")
            
            # Focus fenêtre avant extraction
            window_position = self.platform_profile.get('window_position', {})
            if window_position:
                self.debug_log(f"Focus fenêtre avant extraction: ({window_position['x']}, {window_position['y']})")
                self.conductor.mouse_controller.click(window_position['x'], window_position['y'])
                time.sleep(0.2)
            
            selectors = [primary_selector] + fallback_selectors[:3]
            self.debug_log(f"Sélecteurs fallback à tester: {selectors}")
            
            # Script d'extraction simple
            js_code = f'''
            let selectors = {json.dumps(selectors)};
            console.log("🔄 Testing fallback selectors:", selectors);
            
            for (let i = 0; i < selectors.length; i++) {{
                let selector = selectors[i];
                console.log("Testing selector " + (i+1) + ":", selector);
                
                try {{
                    let elements = document.querySelectorAll(selector);
                    console.log("Found " + elements.length + " elements for selector:", selector);
                    
                    if (elements.length > 0) {{
                        let element = elements[elements.length - 1];
                        let text = (element.textContent || '').trim();
                        
                        console.log("Text length:", text.length);
                        console.log("Text preview:", text.substring(0, 50));
                        
                        if (text.length > 15 && 
                            !text.includes('console.log') && 
                            !text.includes('function()') &&
                            !text.includes('Testing selector')) {{
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
            '''
            
            return self._execute_extraction_script(js_code)
            
        except Exception as e:
            self.debug_log(f"❌ Erreur extraction fallback: {e}")
            logger.error(f"Erreur extraction fallback: {e}")
            try:
                self.conductor.keyboard_controller.press_key('f12')
            except:
                pass
            return ""

    def _execute_detection_script(self, js_code):
        """Exécute le script de détection et surveille les résultats"""
        try:
            self.debug_log(f"🖥️ Ouverture console ({self.detected_browser_type})")
            
            if self.detected_browser_type == 'firefox':
                self.conductor.keyboard_controller.hotkey('ctrl', 'shift', 'k')
            else:
                self.conductor.keyboard_controller.hotkey('ctrl', 'shift', 'j')
            time.sleep(0.5)
            
            if self.should_stop:
                self.debug_log("🛑 Arrêt pendant ouverture console")
                return False
            
            self.debug_log("🧹 Nettoyage console")
            pyperclip.copy("console.clear();")
            self.conductor.keyboard_controller.hotkey('ctrl', 'v')
            self.conductor.keyboard_controller.press_key('enter')
            time.sleep(0.2)
            
            self.debug_log("💉 Injection script de détection")
            pyperclip.copy(js_code)
            self.conductor.keyboard_controller.hotkey('ctrl', 'v')
            self.conductor.keyboard_controller.press_key('enter')
            time.sleep(0.5)
            
            max_wait = 20
            waited = 0
            check_interval = 0.5
            
            self.debug_log(f"👀 Surveillance console (max {max_wait}s, check chaque {check_interval}s)")
            
            while waited < max_wait and not self.should_stop:
                self.conductor.keyboard_controller.hotkey('ctrl', 'a')
                self.conductor.keyboard_controller.hotkey('ctrl', 'c')
                console_content = pyperclip.paste()
                
                self.debug_log(f"Console content length: {len(console_content)}")
                
                for line in console_content.split('\n'):
                    if 'LIRIS_DETECTION_COMPLETE:' in line:
                        status = line.split('LIRIS_DETECTION_COMPLETE:')[1].strip()
                        self.debug_log(f"🎯 Marqueur trouvé: {status}")
                        
                        self.conductor.keyboard_controller.press_key('f12')
                        time.sleep(0.1)
                        
                        if status == 'success':
                            self.debug_log(f"✅ Détection réussie après {waited:.1f}s")
                            logger.info(f"✅ Détection réussie après {waited:.1f}s")
                            return True
                        elif status == 'timeout':
                            self.debug_log(f"⏱️ Détection timeout après {waited:.1f}s")
                            logger.warning(f"⏱️ Détection timeout après {waited:.1f}s")
                            return False
                        else:
                            self.debug_log(f"❌ Détection erreur: {status}")
                            logger.error(f"❌ Détection erreur: {status}")
                            return False
                
                time.sleep(check_interval)
                waited += check_interval
                
                if waited % 2 == 0:
                    self.debug_log(f"⏳ Attente détection... {waited:.1f}s/{max_wait}s")
            
            self.conductor.keyboard_controller.press_key('f12')
            self.debug_log(f"⏱️ Timeout global détection après {waited:.1f}s")
            logger.warning(f"⏱️ Timeout global détection après {waited:.1f}s")
            return False
            
        except Exception as e:
            self.debug_log(f"❌ Erreur exécution détection: {e}")
            logger.error(f"❌ Erreur exécution détection: {e}")
            try:
                self.conductor.keyboard_controller.press_key('f12')
            except:
                pass
            return False

    # 🔄 MÉTHODES FALLBACK - Garder les anciennes méthodes pour compatibilité
    def _get_chatgpt_detection_script(self):
        """Ancienne méthode ChatGPT en fallback"""
        return '''
        (function() {
            let lastDataState = '';
            let stableCount = 0;
            let checkCount = 0;
            let maxChecks = 50;
            
            function checkDataStability() {
                try {
                    checkCount++;
                    if (checkCount > maxChecks) {
                        console.log("LIRIS_DETECTION_COMPLETE:timeout");
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
                            console.log("LIRIS_DETECTION_COMPLETE:success");
                            return;
                        }
                    } else {
                        lastDataState = currentState;
                        stableCount = 0;
                    }
                    
                    setTimeout(checkDataStability, 300);
                } catch(e) {
                    console.log("LIRIS_DETECTION_COMPLETE:error");
                }
            }

            checkDataStability();
            return "ChatGPT detection started";
        })();
        '''
    
    def _get_gemini_detection_script(self):
        """Ancienne méthode Gemini en fallback"""
        return '''
        (function() {
            let lastContentState = '';
            let stableCount = 0;
            let checkCount = 0;
            let maxChecks = 50;
            
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
        '''
    
    def _get_claude_detection_script(self):
        """Ancienne méthode Claude en fallback"""
        return '''
        (function() {
            let checkCount = 0;
            let maxChecks = 50;
            
            function checkClaudeCompletion() {
                try {
                    checkCount++;
                    if (checkCount > maxChecks) {
                        console.log("LIRIS_DETECTION_COMPLETE:timeout");
                        return;
                    }
                    
                    let streamingElements = document.querySelectorAll('[data-is-streaming="true"]');
                    let completedElements = document.querySelectorAll('[data-is-streaming="false"]');
                    
                    if (streamingElements.length === 0 && completedElements.length > 0) {
                        console.log("LIRIS_DETECTION_COMPLETE:success");
                        return;
                    }
                    
                    setTimeout(checkClaudeCompletion, 300);
                } catch(e) {
                    console.log("LIRIS_DETECTION_COMPLETE:error");
                }
            }

            checkClaudeCompletion();
            return "Claude detection started";
        })();
        '''
    
    def _get_generic_detection_script(self, selector):
        """Ancienne méthode générique en fallback"""
        return f'''
        (function() {{
            let lastText = '';
            let stableCount = 0;
            let checkCount = 0;
            let maxChecks = 40;
            
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


class FinalTestWidget(QtWidgets.QWidget):

    test_completed = pyqtSignal(str, bool, str)
    response_received = pyqtSignal(str, str)
    detection_config_saved = pyqtSignal(str, dict)

    def __init__(self, config_provider, conductor, keyboard_config_widget=None, parent=None):
        super().__init__(parent)
        self.config_provider = config_provider
        self.conductor = conductor

        # NOUVEAU : Initialiser le générateur universel
        self.selector_generator = UniversalSelectorGenerator()

        self.keyboard_config_widget = keyboard_config_widget
        self.keyboard_config = {}

        self.current_platform = None
        self.profiles = {}
        self.current_profile = None

        self.test_running = False
        self.temp_detection_config = {}
        self.temp_test_result = ""

        self.detected_browser_type = "chrome"
        
        self.test_worker = None

        if self.keyboard_config_widget:
            try:
                self.keyboard_config_widget.keyboard_configured.connect(self._update_keyboard_config)
                self._update_keyboard_config(self.keyboard_config_widget._get_current_config())
            except Exception as e:
                logger.warning(f"Impossible de connecter la configuration clavier: {e}")
                self.keyboard_config_widget = None

        self._init_ui()

    def _init_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        left_layout = QtWidgets.QVBoxLayout()
        left_layout.setSpacing(15)

        platform_group = QtWidgets.QGroupBox("🎯 Plateforme")
        platform_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        platform_layout = QtWidgets.QVBoxLayout(platform_group)

        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.currentTextChanged.connect(self._on_platform_changed)
        platform_layout.addWidget(self.platform_combo)

        self.platform_status = QtWidgets.QLabel("Sélectionnez une plateforme...")
        self.platform_status.setWordWrap(True)
        platform_layout.addWidget(self.platform_status)

        self.browser_status = QtWidgets.QLabel("Navigateur: Non détecté")
        self.browser_status.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")
        platform_layout.addWidget(self.browser_status)

        self.sync_status = QtWidgets.QLabel("Synchronisation: En attente")
        self.sync_status.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")
        platform_layout.addWidget(self.sync_status)

        if self.keyboard_config_widget:
            self.alt_tab_status = QtWidgets.QLabel("Protection Alt+Tab: Non configurée")
            self.alt_tab_status.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")
            platform_layout.addWidget(self.alt_tab_status)
            self._update_alt_tab_status()

        left_layout.addWidget(platform_group)

        config_status_group = QtWidgets.QGroupBox("🔍 Configuration Détection Universelle")
        config_status_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        config_status_layout = QtWidgets.QVBoxLayout(config_status_group)

        self.detection_phase_status = QtWidgets.QLabel("⏳ Chargement configuration universelle...")
        self.detection_phase_status.setWordWrap(True)
        config_status_layout.addWidget(self.detection_phase_status)

        self.force_reload_btn = QtWidgets.QPushButton("🔄 Recharger Config")
        self.force_reload_btn.setStyleSheet("""
            QPushButton {
                background-color: #6f42c1;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #5a2e9c; }
        """)
        self.force_reload_btn.clicked.connect(self._force_reload_from_database)
        config_status_layout.addWidget(self.force_reload_btn)

        left_layout.addWidget(config_status_group)

        test_actions_group = QtWidgets.QGroupBox("🚀 Test Final Universel")
        test_actions_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        test_actions_layout = QtWidgets.QVBoxLayout(test_actions_group)

        prompt_label = QtWidgets.QLabel("Message de test :")
        prompt_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        test_actions_layout.addWidget(prompt_label)

        self.final_test_prompt = QtWidgets.QLineEdit("Bonjour ! Dites simplement 'Hello' pour tester.")
        self.final_test_prompt.setPlaceholderText("Prompt pour test final...")
        test_actions_layout.addWidget(self.final_test_prompt)

        self.start_final_test_btn = QtWidgets.QPushButton("🚀 Test Final Universel")
        self.start_final_test_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 12px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #0056b3; }
            QPushButton:disabled { background-color: #6c757d; }
        """)
        self.start_final_test_btn.clicked.connect(self._start_final_test)
        self.start_final_test_btn.setEnabled(False)
        test_actions_layout.addWidget(self.start_final_test_btn)

        self.stop_test_btn = QtWidgets.QPushButton("⏹️ Arrêter Test")
        self.stop_test_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #c82333; }
        """)
        self.stop_test_btn.clicked.connect(self._stop_test)
        self.stop_test_btn.setVisible(False)
        test_actions_layout.addWidget(self.stop_test_btn)

        self.test_phase_status = QtWidgets.QLabel("⏳ Sélectionnez une plateforme configurée")
        self.test_phase_status.setWordWrap(True)
        test_actions_layout.addWidget(self.test_phase_status)

        left_layout.addWidget(test_actions_group)

        validation_group = QtWidgets.QGroupBox("✅ Validation")
        validation_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        validation_layout = QtWidgets.QVBoxLayout(validation_group)

        self.validate_success_btn = QtWidgets.QPushButton("✅ Valider - Config OK")
        self.validate_success_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:disabled { background-color: #6c757d; }
        """)
        self.validate_success_btn.clicked.connect(self._validate_success)
        self.validate_success_btn.setEnabled(False)
        validation_layout.addWidget(self.validate_success_btn)

        self.validate_retry_btn = QtWidgets.QPushButton("🔄 Reconfigurer")
        self.validate_retry_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #F57C00; }
            QPushButton:disabled { background-color: #6c757d; }
        """)
        self.validate_retry_btn.clicked.connect(self._retry_configuration)
        self.validate_retry_btn.setEnabled(False)
        validation_layout.addWidget(self.validate_retry_btn)

        self.validation_status = QtWidgets.QLabel("⏳ Effectuez d'abord le test")
        self.validation_status.setWordWrap(True)
        validation_layout.addWidget(self.validation_status)

        left_layout.addWidget(validation_group)
        left_layout.addStretch(1)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.setSpacing(15)

        header = QtWidgets.QLabel(
            "<b>🎯 Test Final Universel</b><br>"
            "<b style='color: #007bff;'>⚡ Workflow Direct : Clic icône → Clic champ → Prompt → Détection Universelle → Extraction Universelle</b><br>"
            "<b style='color: #28a745;'>✅ Générateur universel de sélecteurs intégré</b>"
        )
        header.setWordWrap(True)
        header.setStyleSheet(PlatformConfigStyle.get_explanation_style())
        right_layout.addWidget(header)

        sync_config_group = QtWidgets.QGroupBox("🔄 Configuration Universelle Utilisée")
        sync_config_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        sync_config_layout = QtWidgets.QVBoxLayout(sync_config_group)

        sync_instructions = QtWidgets.QLabel(
            "<b>🔄 WORKFLOW UNIVERSEL :</b><br>"
            "• Clic icône fenêtre → Utilise window_position configurées<br>"
            "• Clic champ de saisie → Utilise interface_positions<br>"
            "• Envoi prompt utilisateur → Contrôleurs directs<br>"
            "• Détection de fin → Via sélecteurs universels spécialisés<br>"
            "• Extraction console → Sélecteurs CSS universels configurés<br>"
            "<b style='color: #28a745;'>✅ Logique universelle auto-adaptative !</b>"
        )
        sync_instructions.setWordWrap(True)
        sync_instructions.setStyleSheet("color: #2196F3; font-size: 10px; margin-bottom: 10px;")
        sync_config_layout.addWidget(sync_instructions)

        detection_label = QtWidgets.QLabel("🎯 Configuration Détection Universelle :")
        detection_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        sync_config_layout.addWidget(detection_label)

        self.detection_config_display = QtWidgets.QTextEdit()
        self.detection_config_display.setMaximumHeight(100)
        self.detection_config_display.setReadOnly(True)
        self.detection_config_display.setStyleSheet(
            "background-color: #f8f8f8; border: 1px solid #ddd; font-family: 'Consolas', monospace; font-size: 10px;"
        )
        self.detection_config_display.setPlaceholderText("Configuration détection universelle apparaîtra ici...")
        sync_config_layout.addWidget(self.detection_config_display)

        extraction_label = QtWidgets.QLabel("📄 Configuration Extraction Universelle :")
        extraction_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        sync_config_layout.addWidget(extraction_label)

        self.extraction_config_display = QtWidgets.QTextEdit()
        self.extraction_config_display.setMaximumHeight(80)
        self.extraction_config_display.setReadOnly(True)
        self.extraction_config_display.setStyleSheet(
            "background-color: #f0f8ff; border: 1px solid #007bff; font-family: 'Consolas', monospace; font-size: 10px;"
        )
        self.extraction_config_display.setPlaceholderText("Configuration extraction universelle apparaîtra ici...")
        sync_config_layout.addWidget(self.extraction_config_display)

        right_layout.addWidget(sync_config_group)

        response_group = QtWidgets.QGroupBox("🤖 Réponse IA Extraite")
        response_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        response_layout = QtWidgets.QVBoxLayout(response_group)

        self.extracted_response = QtWidgets.QTextEdit()
        self.extracted_response.setMaximumHeight(150)
        self.extracted_response.setReadOnly(True)
        self.extracted_response.setStyleSheet(
            "background-color: #f0f8ff; border: 2px solid #4CAF50; border-radius: 4px; padding: 8px;"
        )
        self.extracted_response.setPlaceholderText("Réponse IA extraite...")
        response_layout.addWidget(self.extracted_response)

        right_layout.addWidget(response_group)
        right_layout.addStretch(1)

        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setMaximumWidth(350)

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_layout)

        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget, 1)

    def _update_keyboard_config(self, config):
        if not config:
            return

        self.keyboard_config = config
        logger.info(f"Configuration clavier mise à jour: {json.dumps(config, indent=2)}")

        if hasattr(self, 'alt_tab_status'):
            self._update_alt_tab_status()

    def _update_alt_tab_status(self):
        if not hasattr(self, 'alt_tab_status'):
            return

        if self.keyboard_config.get('block_alt_tab', False):
            self.alt_tab_status.setText("Protection Alt+Tab: Activée")
            self.alt_tab_status.setStyleSheet("color: #28a745; font-size: 10px; margin-top: 5px; font-weight: bold;")
        else:
            self.alt_tab_status.setText("Protection Alt+Tab: Désactivée")
            self.alt_tab_status.setStyleSheet("color: #dc3545; font-size: 10px; margin-top: 5px; font-weight: bold;")

    def _detect_browser_type(self):
        try:
            if not self.current_platform or not self.current_profile:
                return "chrome"

            browser_config = self.current_profile.get('browser', {})
            browser_path = browser_config.get('path', '').lower()
            browser_url = browser_config.get('url', '').lower()

            if browser_path:
                if 'chrome' in browser_path:
                    return "chrome"
                elif 'firefox' in browser_path or 'mozilla' in browser_path:
                    return "firefox"
                elif 'edge' in browser_path:
                    return "edge"

            if browser_url:
                if 'chrome' in browser_url:
                    return "chrome"
                elif 'firefox' in browser_url:
                    return "firefox"

            platform_lower = self.current_platform.lower()
            if 'firefox' in platform_lower:
                return "firefox"
            elif 'chrome' in platform_lower:
                return "chrome"
            elif 'edge' in platform_lower:
                return "edge"

            return "chrome"

        except Exception as e:
            logger.error(f"Erreur détection navigateur: {e}")
            return "chrome"

    def _update_browser_status(self):
        self.detected_browser_type = self._detect_browser_type()
        self.browser_status.setText(f"Navigateur détecté: {self.detected_browser_type.capitalize()}")
        self.browser_status.setStyleSheet("color: #007bff; font-size: 10px; margin-top: 5px; font-weight: bold;")
        logger.info(f"🌐 Navigateur détecté: {self.detected_browser_type}")

    def _on_platform_changed(self, platform_name):
        if platform_name and platform_name != "-- Sélectionner --":
            self.current_platform = platform_name
            self.current_profile = self.profiles.get(platform_name, {})
            self._update_platform_status()
            self._update_browser_status()
            self._load_and_sync_configuration()
        else:
            self.current_platform = None
            self.current_profile = None
            self._reset_interface()

        self._update_test_button_state()

    def _load_and_sync_configuration(self):
        if not self.current_platform or not self.current_profile:
            return

        try:
            logger.info(f"🔄 Synchronisation configuration universelle pour {self.current_platform}")
            
            fresh_profile = self._get_fresh_profile_from_database()
            if fresh_profile:
                self.current_profile = fresh_profile
                self.profiles[self.current_platform] = fresh_profile
                logger.info("✅ Profil rechargé et synchronisé")
            else:
                logger.warning("⚠️ Impossible de recharger le profil")

            window_pos = self.current_profile.get('window_position')
            interface_pos = self.current_profile.get('interface_positions', {})
            extraction_conf = self.current_profile.get('extraction_config', {})
            
            logger.info(f"🔍 DEBUG - window_position: {window_pos}")
            logger.info(f"🔍 DEBUG - interface_positions: {bool(interface_pos)}")
            logger.info(f"🔍 DEBUG - extraction_config: {bool(extraction_conf)}")

            extraction_config = self._get_extraction_config_from_response_area()
            detection_config = self.current_profile.get('detection_config', {})

            # 🎯 NOUVEAU : Vérification configuration universelle
            response_area = extraction_config or {}
            universal_config = response_area.get('universal_config')

            if universal_config:
                self.sync_status.setText("✅ Sync: Configuration universelle détectée")
                self.sync_status.setStyleSheet("color: #28a745; font-size: 10px; margin-top: 5px; font-weight: bold;")
                logger.info(f"🎯 Configuration universelle trouvée pour {universal_config.get('platform', 'Unknown')}")
            elif extraction_config and not detection_config:
                logger.info("📋 Création automatique config détection depuis extraction")
                detection_config = self._create_detection_from_extraction(extraction_config)
                if detection_config:
                    self.current_profile['detection_config'] = detection_config
                    self._save_profile_to_database()
                    self.sync_status.setText("✅ Sync: Détection créée automatiquement")
                    self.sync_status.setStyleSheet("color: #28a745; font-size: 10px; margin-top: 5px; font-weight: bold;")
            elif extraction_config and detection_config:
                self.sync_status.setText("✅ Sync: Configurations cohérentes")
                self.sync_status.setStyleSheet("color: #28a745; font-size: 10px; margin-top: 5px; font-weight: bold;")
            else:
                self.sync_status.setText("❌ Sync: Configuration incomplète")
                self.sync_status.setStyleSheet("color: #dc3545; font-size: 10px; margin-top: 5px; font-weight: bold;")

            self._display_synchronized_configurations(detection_config, extraction_config)

            if detection_config:
                self.temp_detection_config = detection_config

            logger.info("✅ Synchronisation universelle terminée")

        except Exception as e:
            logger.error(f"Erreur synchronisation: {e}")
            self.sync_status.setText("❌ Sync: Erreur")
            self.sync_status.setStyleSheet("color: #dc3545; font-size: 10px; margin-top: 5px; font-weight: bold;")

    def _get_fresh_profile_from_database(self):
        try:
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'get_platform'):
                    fresh_profile = self.conductor.database.get_platform(self.current_platform)
                    if fresh_profile:
                        logger.info(f"✅ Profil rechargé depuis DB pour {self.current_platform}")
                        return fresh_profile
            
            if hasattr(self.config_provider, 'profiles'):
                memory_profile = self.config_provider.profiles.get(self.current_platform)
                if memory_profile:
                    logger.info(f"✅ Profil récupéré depuis config_provider pour {self.current_platform}")
                    return memory_profile
            
            local_profile = self.profiles.get(self.current_platform)
            if local_profile:
                logger.info(f"✅ Profil récupéré depuis cache local pour {self.current_platform}")
                return local_profile
            
            logger.warning(f"❌ Aucun profil trouvé pour {self.current_platform}")
            return None
            
        except Exception as e:
            logger.error(f"Erreur récupération profil {self.current_platform}: {e}")
            return None

    def _get_extraction_config_from_response_area(self):
        try:
            extraction_config = self.current_profile.get('extraction_config', {})
            response_area = extraction_config.get('response_area', {})

            if response_area and response_area.get('platform_config'):
                logger.info("✅ Configuration extraction trouvée depuis Response Area")
                return response_area

            return None
        except Exception as e:
            logger.error(f"Erreur récupération extraction config: {e}")
            return None

    def _create_detection_from_extraction(self, extraction_config):
        try:
            platform_config = extraction_config.get('platform_config', {})
            platform_type = extraction_config.get('platform_type', 'Unknown')

            detection_config = {
                'platform_type': platform_type,
                'primary_selector': platform_config.get('primary_selector', 'p:last-child'),
                'fallback_selectors': platform_config.get('fallback_selectors', ['div:last-child']),
                'detection_method': 'css_selector',
                'configured_at': time.time(),
                'auto_generated_from': 'extraction_config',
                'description': f'Configuration détection auto-générée pour {platform_type}'
            }

            logger.info(f"🔄 Config détection créée pour {platform_type}")
            return detection_config

        except Exception as e:
            logger.error(f"Erreur création config détection: {e}")
            return None

    def _display_synchronized_configurations(self, detection_config, extraction_config):
        try:
            # 🎯 NOUVEAU : Affichage intelligent selon le type de configuration
            if extraction_config and extraction_config.get('universal_config'):
                self._display_universal_configurations(extraction_config['universal_config'])
            else:
                self._display_legacy_configurations(detection_config, extraction_config)

        except Exception as e:
            logger.error(f"Erreur affichage configs: {e}")

    def _display_universal_configurations(self, universal_config):
        """Affiche les configurations universelles"""
        try:
            platform = universal_config.get('platform', 'Unknown')
            detection = universal_config.get('detection', {})
            extraction = universal_config.get('extraction', {})

            # Configuration détection
            detection_text = f"🎯 DÉTECTION UNIVERSELLE - {platform.upper()}\n"
            detection_text += f"Sélecteur principal: {detection.get('primary_selector', 'Non défini')}\n"
            detection_text += f"Méthode: {detection.get('method', 'Non défini')}\n"
            fallback_detection = detection.get('fallback_selectors', [])
            if fallback_detection:
                detection_text += f"Fallbacks: {', '.join(fallback_detection[:2])}\n"
            detection_text += f"Type script: {detection.get('script_type', 'Non défini')}"

            self.detection_config_display.setPlainText(detection_text)
            self.detection_phase_status.setText("✅ Configuration détection universelle synchronisée")
            self.detection_phase_status.setStyleSheet("color: #28a745; font-weight: bold;")

            # Configuration extraction
            extraction_text = f"🎯 EXTRACTION UNIVERSELLE - {platform.upper()}\n"
            extraction_text += f"Sélecteur principal: {extraction.get('primary_selector', 'Non défini')}\n"
            extraction_text += f"Nettoyage: {extraction.get('text_cleaning', 'Non défini')}\n"
            fallback_extraction = extraction.get('fallback_selectors', [])
            if fallback_extraction:
                extraction_text += f"Fallbacks: {', '.join(fallback_extraction[:2])}\n"
            extraction_text += f"Description: {extraction.get('description', 'Non définie')}"

            self.extraction_config_display.setPlainText(extraction_text)

            logger.info(f"✅ Configurations universelles affichées pour {platform}")

        except Exception as e:
            logger.error(f"Erreur affichage configurations universelles: {e}")

    def _display_legacy_configurations(self, detection_config, extraction_config):
        """Affiche les configurations legacy"""
        try:
            if detection_config:
                detection_text = f"📋 DÉTECTION LEGACY\n"
                detection_text += f"Sélecteur principal: {detection_config.get('primary_selector', 'Non défini')}\n"
                fallback_selectors = detection_config.get('fallback_selectors', [])
                if fallback_selectors:
                    detection_text += f"Sélecteurs fallback: {', '.join(fallback_selectors[:2])}\n"
                detection_text += f"Type plateforme: {detection_config.get('platform_type', 'Générique')}"

                self.detection_config_display.setPlainText(detection_text)
                self.detection_phase_status.setText("✅ Configuration détection legacy synchronisée")
                self.detection_phase_status.setStyleSheet("color: #28a745; font-weight: bold;")
            else:
                self.detection_config_display.setPlainText("Aucune configuration de détection")
                self.detection_phase_status.setText("❌ Configuration détection manquante")
                self.detection_phase_status.setStyleSheet("color: #dc3545; font-weight: bold;")

            if extraction_config:
                platform_config = extraction_config.get('platform_config', {})
                extraction_text = f"📋 EXTRACTION LEGACY\n"
                extraction_text += f"Sélecteur principal: {platform_config.get('primary_selector', 'Non défini')}\n"
                fallback_selectors = platform_config.get('fallback_selectors', [])
                if fallback_selectors:
                    extraction_text += f"Sélecteurs fallback: {', '.join(fallback_selectors[:2])}\n"
                extraction_text += f"Type plateforme: {extraction_config.get('platform_type', 'Générique')}"

                self.extraction_config_display.setPlainText(extraction_text)
            else:
                self.extraction_config_display.setPlainText("Aucune configuration d'extraction")

            logger.info("📋 Configurations legacy affichées")

        except Exception as e:
            logger.error(f"Erreur affichage configurations legacy: {e}")

    def _save_profile_to_database(self):
        try:
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'save_platform'):
                    return self.conductor.database.save_platform(self.current_platform, self.current_profile)
            return True
        except Exception as e:
            logger.error(f"Erreur sauvegarde profil: {e}")
            return False

    def _force_reload_from_database(self):
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucune plateforme sélectionnée")
            return

        try:
            logger.info(f"🔄 Rechargement forcé depuis DB pour {self.current_platform}")

            fresh_profile = self._get_fresh_profile_from_database()
            if fresh_profile:
                self.current_profile = fresh_profile

                if hasattr(self.config_provider, 'profiles'):
                    self.config_provider.profiles[self.current_platform] = fresh_profile

                self._load_and_sync_configuration()

                QtWidgets.QMessageBox.information(
                    self,
                    "Rechargement réussi",
                    f"✅ Configuration rechargée depuis la base de données pour {self.current_platform}"
                )
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Rechargement échoué",
                    f"❌ Impossible de recharger {self.current_platform} depuis la base de données"
                )

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur rechargement:\n{str(e)}")

    def _has_valid_configuration(self):
        if not self.current_platform or not self.current_profile:
            logger.warning("❌ Pas de plateforme ou profil sélectionné")
            return False

        logger.info(f"🔍 Validation config pour {self.current_platform}")
        logger.info(f"📋 Clés profil: {list(self.current_profile.keys())}")

        window_position = self.current_profile.get('window_position')
        logger.info(f"🪟 window_position: {window_position}")
        
        if not window_position or 'x' not in window_position or 'y' not in window_position:
            logger.warning(f"❌ window_position invalide: {window_position}")
            return False

        interface_positions = self.current_profile.get('interface_positions', {})
        prompt_field = interface_positions.get('prompt_field')
        logger.info(f"📝 prompt_field: {prompt_field}")
        
        if not prompt_field or 'center_x' not in prompt_field or 'center_y' not in prompt_field:
            logger.warning(f"❌ prompt_field invalide: {prompt_field}")
            return False

        extraction_config = self.current_profile.get('extraction_config', {})
        logger.info(f"📄 extraction_config: {bool(extraction_config)}")
        
        if not extraction_config:
            logger.warning("❌ extraction_config manquante")
            return False

        logger.info("✅ Configuration complète et valide")
        return True

    def _update_test_button_state(self):
        should_enable = self._has_valid_configuration() and not self.test_running

        self.start_final_test_btn.setEnabled(should_enable)

        if should_enable:
            self.test_phase_status.setText("🚀 PRÊT POUR LE TEST UNIVERSEL")
            self.test_phase_status.setStyleSheet(
                "color: #007bff; font-weight: bold; background-color: #E3F2FD; padding: 8px; border-radius: 4px;")
        else:
            if not self.current_platform:
                self.test_phase_status.setText("⏳ Sélectionnez une plateforme")
            elif not self._has_valid_configuration():
                self.test_phase_status.setText("⏳ Configuration incomplète")
            elif self.test_running:
                self.test_phase_status.setText("🔄 Test universel en cours...")

            self.test_phase_status.setStyleSheet("color: #6c757d; font-weight: normal;")

    def _start_final_test(self):
        if not self.current_platform:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Sélectionnez d'abord une plateforme")
            return

        if not self._has_valid_configuration():
            QtWidgets.QMessageBox.warning(self, "Erreur", "Configuration incomplète")
            return

        if self.test_running:
            return

        if self.keyboard_config_widget and not self.keyboard_config.get('block_alt_tab', False):
            reply = QtWidgets.QMessageBox.warning(
                self, "Avertissement",
                "La protection Alt+Tab est désactivée. Activez-la dans la configuration clavier pour éviter les changements de fenêtre.\n\nContinuer quand même ?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        self.test_running = True
        self._update_test_button_state()

        self.start_final_test_btn.setVisible(False)
        self.stop_test_btn.setVisible(True)

        test_message = self.final_test_prompt.text() or "Test de configuration universelle"

        logger.info(f"🚀 Début test universel pour {self.current_platform}")

        self.test_worker = SimpleTestWorker(
            conductor=self.conductor,
            platform_profile=self.current_profile,
            test_message=test_message,
            detected_browser_type=self.detected_browser_type
        )

        self.test_worker.test_completed.connect(self._on_test_completed)
        self.test_worker.step_update.connect(self._on_step_update)
        self.test_worker.start()

    def _on_step_update(self, step_id, step_message):
        self.test_phase_status.setText(f"🔄 {step_message}")

    def _on_test_completed(self, success, message, duration, response):
        self.test_running = False
        self._reset_test_buttons()

        if success:
            self.extracted_response.setPlainText(response)
            self.temp_test_result = response

            self.test_phase_status.setText(f"✅ {message}")
            self.test_phase_status.setStyleSheet("color: #28a745; font-weight: bold;")

            self.validate_success_btn.setEnabled(True)
            self.validate_retry_btn.setEnabled(True)
            self.validation_status.setText("✅ Test universel terminé - Validez le résultat")

            logger.info(f"✅ Test universel réussi en {duration:.1f}s")

        else:
            self.test_phase_status.setText(f"❌ {message}")
            self.test_phase_status.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.validation_status.setText("❌ Test universel échoué - Reconfiguration nécessaire")

            logger.error(f"❌ Test universel échoué: {message}")

        if self.test_worker:
            self.test_worker.deleteLater()
            self.test_worker = None

    def _stop_test(self):
        if self.test_running and self.test_worker:
            logger.info("⏹️ Arrêt du test universel demandé")
            
            self.test_worker.stop_test()
            
            QTimer.singleShot(1000, lambda: self._force_stop_test())

    def _force_stop_test(self):
        if self.test_worker and self.test_worker.isRunning():
            self.test_worker.terminate()
            self.test_worker.wait(2000)
            
        self.test_running = False
        self._reset_test_buttons()
        self.test_phase_status.setText("🛑 Test universel arrêté")
        
        if self.test_worker:
            self.test_worker.deleteLater()
            self.test_worker = None

    def _reset_test_buttons(self):
        self.test_running = False
        self.start_final_test_btn.setVisible(True)
        self.stop_test_btn.setVisible(False)
        self._update_test_button_state()

    def _validate_success(self):
        reply = QtWidgets.QMessageBox.question(
            self, "Validation",
            "Confirmez-vous que la configuration universelle fonctionne correctement ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            self._save_final_configuration()

    def _save_final_configuration(self):
        try:
            if self.temp_detection_config:
                self.current_profile['detection_config'] = self.temp_detection_config
                self._save_profile_to_database()

            self.validation_status.setText("✅ Configuration universelle validée")
            self.validate_success_btn.setEnabled(False)
            self.validate_retry_btn.setEnabled(False)

            QtWidgets.QMessageBox.information(self, "Validé", "✅ Configuration universelle validée et sauvegardée !")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Échec sauvegarde:\n{str(e)}")

    def _retry_configuration(self):
        self.temp_detection_config = {}
        self.temp_test_result = ""

        self.extracted_response.clear()

        self.detection_phase_status.setText("📋 Reconfiguration demandée")
        self.test_phase_status.setText("⏳ Synchronisez d'abord la configuration")
        self.validation_status.setText("⏳ Effectuez d'abord le test")

        self.validate_success_btn.setEnabled(False)
        self.validate_retry_btn.setEnabled(False)

        self._load_and_sync_configuration()
        self._update_test_button_state()

    def _update_platform_status(self):
        if not self.current_platform or not self.current_profile:
            self.platform_status.setText("Sélectionnez une plateforme...")
            return

        logger.info(f"🔍 Mise à jour statut pour {self.current_platform}")
        
        browser_config = self.current_profile.get('browser', {})
        interface_positions = self.current_profile.get('interface_positions', {})
        window_position = self.current_profile.get('window_position')
        extraction_config = self.current_profile.get('extraction_config', {})

        logger.info(f"🌐 browser_config: {bool(browser_config)} (URL: {browser_config.get('url', 'N/A')})")
        logger.info(f"🪟 window_position: {window_position}")
        logger.info(f"📝 interface_positions: {bool(interface_positions)}")
        logger.info(f"📄 extraction_config: {bool(extraction_config)}")

        missing = []
        
        if not browser_config.get('url'):
            missing.append("URL navigateur")
            
        if not window_position or not window_position.get('x') or not window_position.get('y'):
            missing.append("Position fenêtre")
            
        if not interface_positions.get('prompt_field'):
            missing.append("Position champ prompt")
            
        if not extraction_config:
            missing.append("Configuration extraction")

        if missing:
            missing_text = ', '.join(missing)
            self.platform_status.setText(f"⚠️ Manque: {missing_text}")
            self.platform_status.setStyleSheet("color: #FF9800; font-weight: bold;")
            logger.warning(f"❌ Éléments manquants: {missing_text}")
        else:
            self.platform_status.setText("✅ Plateforme configurée")
            self.platform_status.setStyleSheet("color: #28a745; font-weight: bold;")
            logger.info("✅ Plateforme complètement configurée")

    def _reset_interface(self):
        self.temp_detection_config = {}
        self.temp_test_result = ""
        self.detected_browser_type = "chrome"

        self.platform_status.setText("Sélectionnez une plateforme...")
        self.browser_status.setText("Navigateur: Non détecté")
        self.browser_status.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")

        self.sync_status.setText("Synchronisation: En attente")
        self.sync_status.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")

        if hasattr(self, 'alt_tab_status'):
            self.alt_tab_status.setText("Protection Alt+Tab: Non configurée")
            self.alt_tab_status.setStyleSheet("color: #666; font-size: 10px; margin-top: 5px;")

        self.detection_phase_status.setText("⏳ Chargement configuration universelle...")
        self.test_phase_status.setText("⏳ Sélectionnez une plateforme configurée")
        self.validation_status.setText("⏳ Effectuez d'abord le test")

        self.detection_config_display.clear()
        self.extraction_config_display.clear()
        self.extracted_response.clear()

        self.validate_success_btn.setEnabled(False)
        self.validate_retry_btn.setEnabled(False)

        self._update_test_button_state()

    def closeEvent(self, event):
        try:
            if self.test_running and self.test_worker:
                self.test_worker.stop_test()
                if self.test_worker.isRunning():
                    self.test_worker.terminate()
                    self.test_worker.wait(1000)
        except Exception as e:
            logger.debug(f"Erreur nettoyage: {e}")
        super().closeEvent(event)

    def set_profiles(self, profiles):
        self.profiles = profiles or {}

        current_text = self.platform_combo.currentText()
        self.platform_combo.clear()
        self.platform_combo.addItem("-- Sélectionner --")

        for name in sorted(self.profiles.keys()):
            self.platform_combo.addItem(name)

        if current_text:
            index = self.platform_combo.findText(current_text)
            if index >= 0:
                self.platform_combo.setCurrentIndex(index)

    def select_platform(self, platform_name):
        index = self.platform_combo.findText(platform_name)
        if index >= 0:
            self.platform_combo.setCurrentIndex(index)

    def refresh(self):
        self.set_profiles(self.profiles)
        if self.keyboard_config_widget:
            try:
                self._update_keyboard_config(self.keyboard_config_widget._get_current_config())
            except Exception as e:
                logger.warning(f"Erreur refresh config clavier: {e}")

    def force_sync_from_response_area(self, platform_name):
        if platform_name == self.current_platform:
            logger.info(f"🔄 Synchronisation forcée demandée pour {platform_name}")
            self._load_and_sync_configuration()