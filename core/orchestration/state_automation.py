#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
core/orchestration/state_automation.py
"""

import time
import json
import pyperclip
from PyQt5.QtCore import QObject, pyqtSignal
from utils.logger import logger

try:
    import pygetwindow as gw
    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False


class StateBasedAutomation(QObject):
    step_completed = pyqtSignal(str, str)
    automation_completed = pyqtSignal(bool, str, float, str)
    automation_failed = pyqtSignal(str, str)

    def __init__(self, detector, mouse_controller, keyboard_controller, conductor):
        super().__init__()
        self.detector = detector
        self.mouse_controller = mouse_controller
        self.keyboard_controller = keyboard_controller
        self.conductor = conductor

        self.is_running = False
        self.force_stop = False
        self.start_time = None

        self.platform_profile = None
        self.test_text = ""
        self.skip_browser_activation = False
        self.extracted_response = ""
        self.browser_type = "chrome"

        self.browser_config = {}
        self.selected_window = None
        self.window_selection_method = "auto"

    def start_test_automation(self, platform_profile, num_tabs, browser_type, url, automation_params=None):
        if self.is_running:
            return

        self.platform_profile = platform_profile
        self.browser_type = browser_type or "chrome"
        self.test_text = (automation_params or {}).get('test_text', 'Test')
        self.skip_browser_activation = (automation_params or {}).get('skip_browser_activation', False)
        self.extracted_response = ""

        self.load_window_config()

        self.is_running = True
        self.force_stop = False
        self.start_time = time.time()

        try:
            self.run_automation_sequence()
        except Exception as e:
            self.handle_failure(f"Sequence error: {str(e)}")

    def load_window_config(self):
        try:
            if not self.platform_profile:
                return

            self.browser_config = self.platform_profile.get('browser', {})

            if 'window_selection_method' not in self.browser_config:
                self.browser_config.update({
                    'window_selection_method': 'auto',
                    'window_order': 1,
                    'window_title_pattern': '',
                    'window_position': None,
                    'window_id': None,
                    'window_size': None,
                    'remember_window': False
                })

            self.window_selection_method = self.browser_config.get('window_selection_method', 'auto')

        except Exception:
            self.window_selection_method = 'auto'
            self.browser_config = {}

    def get_target_window(self):
        try:
            if self.window_selection_method == 'auto' or not self.browser_config:
                return None

            if not hasattr(self.conductor, 'window_manager'):
                return None

            if not HAS_PYGETWINDOW:
                return None

            selected_window = self.conductor.window_manager.select_window(
                self.browser_config,
                self.browser_type
            )

            if selected_window:
                return selected_window
            else:
                return None

        except Exception:
            return None

    def focus_window(self, target_window):
        try:
            if not target_window:
                return False

            try:
                target_window.activate()
                time.sleep(0.3)
                return True
            except Exception:
                pass

            try:
                click_x = target_window.left + (target_window.width // 2)
                click_y = target_window.top + 50

                self.mouse_controller.click(click_x, click_y)
                time.sleep(0.2)
                return True
            except Exception:
                pass

            return False

        except Exception:
            return False

    def remember_window_if_needed(self):
        try:
            if not self.browser_config.get('remember_window', False):
                return

            if not self.selected_window:
                return

            if not hasattr(self.conductor, 'remember_window_selection'):
                return

            platform_name = self.platform_profile.get('name', '')
            if platform_name:
                self.conductor.remember_window_selection(
                    platform_name,
                    self.selected_window,
                    self.browser_config
                )

        except Exception:
            pass

    def run_automation_sequence(self):
        try:
            if not self.ensure_browser_focus():
                return

            if not self.click_prompt_field():
                return

            if not self.clear_field():
                return

            if not self.input_text():
                return

            if not self.submit_form():
                return

            if not self.wait_for_response():
                return

            if not self.extract_response():
                return

            self.handle_success()

        except Exception as e:
            self.handle_failure(f"Sequence error: {str(e)}")

    def ensure_browser_focus(self):
        if self.force_stop:
            return False

        self.step_completed.emit("browser_focusing", "Browser focus")

        try:
            if self.skip_browser_activation:
                time.sleep(0.3)
                return True

            self.selected_window = self.get_target_window()

            if self.selected_window:
                if self.focus_window(self.selected_window):
                    self.remember_window_if_needed()
                    return True

            try:
                import tkinter as tk
                root = tk.Tk()
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                root.destroy()

                click_x = screen_width // 2
                click_y = 200
            except:
                click_x = 960
                click_y = 200

            self.mouse_controller.click(click_x, click_y)
            time.sleep(0.2)

            return True

        except Exception:
            return True

    def click_prompt_field(self):
        if self.force_stop:
            return False

        self.step_completed.emit("field_clicking", "Click field")

        try:
            positions = self.platform_profile.get('interface_positions', {})
            prompt_pos = positions.get('prompt_field')

            if not prompt_pos:
                self.handle_failure("Prompt field position missing")
                return False

            x, y = prompt_pos['center_x'], prompt_pos['center_y']

            self.mouse_controller.click(x, y)
            time.sleep(0.2)

            return True

        except Exception as e:
            self.handle_failure(f"Field click error: {str(e)}")
            return False

    def clear_field(self):
        if self.force_stop:
            return False

        self.step_completed.emit("field_clearing", "Clear field")

        try:
            self.keyboard_controller.hotkey('ctrl', 'a')
            time.sleep(0.1)
            self.keyboard_controller.press_key('delete')
            time.sleep(0.1)

            return True

        except Exception as e:
            self.handle_failure(f"Clear error: {str(e)}")
            return False

    def input_text(self):
        if self.force_stop:
            return False

        self.step_completed.emit("text_typing", "Input text")

        try:
            if not self.test_text:
                self.handle_failure("Test text missing")
                return False

            try:
                original_clipboard = pyperclip.paste()
                pyperclip.copy(self.test_text)
                time.sleep(0.05)
                self.keyboard_controller.hotkey('ctrl', 'v')
                time.sleep(0.3)
                pyperclip.copy(original_clipboard)
                return True

            except Exception:
                self.keyboard_controller.type_text(self.test_text)
                time.sleep(0.5)
                return True

        except Exception as e:
            self.handle_failure(f"Input error: {str(e)}")
            return False

    def submit_form(self):
        if self.force_stop:
            return False

        self.step_completed.emit("form_submitting", "Submit")

        try:
            self.keyboard_controller.press_key('enter')
            time.sleep(0.5)
            return True

        except Exception as e:
            self.handle_failure(f"Submit error: {str(e)}")
            return False

    def wait_for_response(self):
        if self.force_stop:
            return False

        self.step_completed.emit("response_waiting", "Wait response")

        try:
            platform_name = self.platform_profile.get('name', '')
            wait_time = self.calculate_wait_time()

            if hasattr(self.conductor, 'wait_for_ai_response'):
                result = self.conductor.wait_for_ai_response(platform_name, wait_time)

                if result.get('detected'):
                    return True
                else:
                    return True
            else:
                time.sleep(wait_time)
                return True

        except Exception:
            return True

    def calculate_wait_time(self):
        try:
            if not self.test_text:
                return 5

            char_count = len(self.test_text)
            word_count = len(self.test_text.split())

            base_time = 2
            char_factor = char_count * 0.05
            word_factor = word_count * 0.15

            calculated_time = base_time + char_factor + word_factor

            min_time = 3
            max_time = 12
            final_time = max(min_time, min(calculated_time, max_time))

            return int(final_time)

        except Exception:
            return 6

    def extract_response(self):
        if self.force_stop:
            return False

        self.step_completed.emit("response_extracting", "Extract")

        try:
            platform_name = self.platform_profile.get('name', '')
            extraction_config = self.get_extraction_config()
            detection_config = self.platform_profile.get('detection_config', {})

            selectors = []

            if extraction_config:
                if 'chatgpt' in platform_name.lower():
                    selectors.extend([
                        'article[data-testid*="conversation-turn"] .markdown.prose',
                        'article[data-testid*="conversation-turn"] .markdown',
                        '[data-message-author-role="assistant"] .markdown.prose',
                        'article[data-testid*="conversation-turn"]:last-child .prose'
                    ])
                else:
                    if extraction_config.get('primary_selector'):
                        selectors.append(extraction_config['primary_selector'])

                    if extraction_config.get('fallback_selectors'):
                        selectors.extend(extraction_config['fallback_selectors'])

            elif detection_config:
                if detection_config.get('primary_selector'):
                    selectors.append(detection_config['primary_selector'])
                if detection_config.get('fallback_selectors'):
                    selectors.extend(detection_config['fallback_selectors'])

            if 'chatgpt' in platform_name.lower():
                selectors.extend([
                    'article[data-testid*="conversation-turn"] .markdown.prose',
                    'article[data-testid*="conversation-turn"]:last-of-type',
                    'article[data-testid="conversation-turn-2"]',
                    'article[data-scroll-anchor="true"]',
                    'article[data-testid*="conversation-turn"]',
                    '[data-message-author-role="assistant"] .markdown.prose',
                    '[data-start][data-end]'
                ])
            else:
                selectors.extend([
                    '[data-message-author-role="assistant"]:last-child',
                    '.message:last-child',
                    '.ai-response:last-child',
                    '[role="assistant"]:last-child',
                    '.markdown:last-child',
                    'p:last-child'
                ])

            js_code = f'''
                let selectors = {json.dumps(selectors[:5])};

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
                                copy(text);
                                break;
                            }}
                        }}
                    }} catch(e) {{ 
                        continue; 
                    }}
                }}
            '''

            if self.execute_javascript(js_code):
                if self.extracted_response and len(self.extracted_response) > 15:
                    return True

            if self.extract_fallback():
                return True

            self.handle_failure("No response extracted")
            return False

        except Exception as e:
            self.handle_failure(f"Extract error: {str(e)}")
            return False

    def get_extraction_config(self):
        try:
            extraction_config = self.platform_profile.get('extraction_config', {})
            if not extraction_config:
                return None

            response_area = extraction_config.get('response_area', {})
            if not response_area:
                return None

            platform_config = response_area.get('platform_config', {})
            if not platform_config:
                return None

            return platform_config

        except Exception:
            return None

    def execute_javascript(self, js_code):
        try:
            if self.selected_window:
                try:
                    self.selected_window.activate()
                    time.sleep(0.2)
                except Exception:
                    pass

            if self.selected_window:
                try:
                    click_x = self.selected_window.left + (self.selected_window.width // 2)
                    click_y = self.selected_window.top + 100
                except Exception:
                    click_x = 960
                    click_y = 540
            else:
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
            time.sleep(0.2)

            if hasattr(self.conductor, 'js_executor'):
                result = self.conductor.js_executor.execute_console_js(js_code, self.browser_type)
                if result:
                    self.extracted_response = result
                    return True
                return False
            else:
                return self.execute_js_fallback(js_code)

        except Exception:
            return False

    def execute_js_fallback(self, js_code):
        try:
            if self.browser_type == 'firefox':
                self.keyboard_controller.hotkey('ctrl', 'shift', 'k')
            else:
                self.keyboard_controller.hotkey('ctrl', 'shift', 'j')
            time.sleep(0.5)

            pyperclip.copy("console.clear();")
            self.keyboard_controller.hotkey('ctrl', 'v')
            self.keyboard_controller.press_key('enter')
            time.sleep(0.1)

            pyperclip.copy(js_code)
            self.keyboard_controller.hotkey('ctrl', 'v')

            platform_name = self.platform_profile.get('name', '').lower()
            if 'gemini' in platform_name:
                self.keyboard_controller.hotkey('ctrl', 'enter')
            else:
                self.keyboard_controller.press_key('enter')

            time.sleep(0.5)
            time.sleep(0.3)

            result = pyperclip.paste().strip()

            if result and len(result) > 15:
                if not any(keyword in result.lower() for keyword in
                           ['function()', 'console.log', 'document.query', 'let ', 'const ', '🎯', 'console.clear']):
                    self.extracted_response = result
                    self.keyboard_controller.press_key('f12')
                    time.sleep(0.1)
                    return True

            self.keyboard_controller.press_key('f12')
            time.sleep(0.1)
            return False

        except Exception:
            try:
                self.keyboard_controller.press_key('f12')
            except:
                pass
            return False

    def extract_fallback(self):
        try:
            js_code = '''
            let chatgptSelectors = [
                'article[data-testid*="conversation-turn"] .markdown.prose',
                'article[data-testid*="conversation-turn"]:last-of-type', 
                'article[data-scroll-anchor="true"]',
                'article[data-testid*="conversation-turn"]'
            ];

            for (let selector of chatgptSelectors) {
                try {
                    let elements = document.querySelectorAll(selector);
                    if (elements.length > 0) {
                        let text = (elements[elements.length - 1].textContent || '').trim();
                        if (text.length > 15 && 
                            !text.includes('function()') && 
                            !text.includes('console.log') &&
                            !text.includes('🎯')) {
                            copy(text);
                            break;
                        }
                    }
                } catch(e) { 
                    continue; 
                }
            }
            '''

            if hasattr(self.conductor, 'js_executor'):
                result = self.conductor.js_executor.execute_console_js(js_code, self.browser_type)
                if result:
                    self.extracted_response = result
                    return True
                return False
            else:
                return self.execute_js_fallback(js_code)

        except Exception:
            return False

    def handle_success(self):
        duration = time.time() - self.start_time
        self.remember_window_if_needed()
        self.is_running = False
        self.automation_completed.emit(True, f"Success in {duration:.1f}s", duration, self.extracted_response)

    def handle_failure(self, error_message):
        duration = time.time() - self.start_time if self.start_time else 0
        self.is_running = False
        self.automation_failed.emit("automation_error", error_message)

    def stop_automation(self):
        self.force_stop = True
        self.is_running = False

        try:
            self.keyboard_controller.press_key('f12')
        except:
            pass

        if hasattr(self.conductor, 'browser_already_active'):
            self.conductor.browser_already_active = False

        self.selected_window = None
        self.window_selection_method = "auto"

        duration = time.time() - self.start_time if self.start_time else 0
        self.automation_completed.emit(False, "Stopped by user", duration, "")

    def get_current_status(self):
        duration = time.time() - self.start_time if self.start_time else 0

        status = {
            'is_running': self.is_running,
            'duration': duration,
            'force_stop': self.force_stop,
            'platform': self.platform_profile.get('name', '') if self.platform_profile else '',
            'extracted_response_length': len(self.extracted_response),
            'window_selection_method': self.window_selection_method,
            'has_selected_window': self.selected_window is not None,
            'selected_window_title': self.selected_window.title if self.selected_window else None,
            'browser_type': self.browser_type
        }

        return status

    def is_automation_running(self):
        return self.is_running and not self.force_stop