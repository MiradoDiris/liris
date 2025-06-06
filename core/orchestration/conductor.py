#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
core/orchestration/conductor.py
"""

import threading
import time
import queue
import os
import json
import random
import pyautogui
import pyperclip
import re
import sys
import subprocess
from datetime import datetime
from utils.logger import logger
from utils.exceptions import OrchestrationError, SchedulingError
from core.orchestration.state_automation import StateBasedAutomation

try:
    import pygetwindow as gw
    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False

try:
    from config.console_shortcuts import open_console_for_browser, close_console_for_browser
    HAS_CONSOLE_SHORTCUTS = True
except ImportError:
    HAS_CONSOLE_SHORTCUTS = False


def random_sleep(base_time, min_variance=0.05, max_variance=0.20):
    variance = random.uniform(min_variance, max_variance)
    if random.choice([True, False]):
        actual_time = base_time * (1 + variance)
    else:
        actual_time = base_time * (1 - variance)
    time.sleep(max(0.1, actual_time))
    return actual_time


class BrowserManager:
    def __init__(self):
        self.last_open_time = 0
        self.min_interval = 3
        self._lock = threading.Lock()
    
    def can_open(self):
        with self._lock:
            return time.time() - self.last_open_time >= self.min_interval
    
    def mark_opened(self):
        with self._lock:
            self.last_open_time = time.time()

    def open_url(self, url, browser_type="chrome", new_window=False):
        if not self.can_open():
            return {"success": True, "skipped": True, "reason": "protection"}
        
        try:
            browser_type_lower = browser_type.lower()
            
            if "firefox" in browser_type_lower:
                if sys.platform == "win32":
                    cmd = f'start firefox {"-new-window" if new_window else ""} "{url}"'
                    os.system(cmd)
                elif sys.platform == "darwin":
                    subprocess.run(["open", "-a", "Firefox", url])
                else:
                    args = ["firefox"]
                    if new_window:
                        args.append("-new-window")
                    args.append(url)
                    subprocess.run(args)
                    
            elif "edge" in browser_type_lower:
                if sys.platform == "win32":
                    cmd = f'start msedge {"--new-window" if new_window else ""} "{url}"'
                    os.system(cmd)
                elif sys.platform == "darwin":
                    subprocess.run(["open", "-a", "Microsoft Edge", url])
                else:
                    subprocess.run(["microsoft-edge", url])
                    
            else:  # Chrome default
                if sys.platform == "win32":
                    cmd = f'start chrome {"--new-window" if new_window else ""} "{url}"'
                    os.system(cmd)
                elif sys.platform == "darwin":
                    subprocess.run(["open", "-a", "Google Chrome", url])
                else:
                    args = ["google-chrome"]
                    if new_window:
                        args.append("--new-window")
                    args.append(url)
                    subprocess.run(args)
        
            self.mark_opened()
            return {"success": True, "method": "new_window" if new_window else "tab"}
            
        except Exception as e:
            try:
                if sys.platform == "win32":
                    os.startfile(url)
                elif sys.platform == "darwin":
                    subprocess.run(["open", url])
                else:
                    subprocess.run(["xdg-open", url])
                
                self.mark_opened()
                return {"success": True, "method": "system_fallback"}
                
            except Exception as e2:
                return {"success": False, "error": str(e2)}


class WindowManager:
    def __init__(self):
        self.cache = {}
        self.cache_timestamp = 0
        self.cache_duration = 5
        self.sort_method = "natural"

    def get_browser_windows(self, browser_type=None, use_cache=True):
        current_time = time.time()
        cache_key = f"{browser_type or 'all'}_{self.sort_method}"
        
        if (use_cache and 
            cache_key in self.cache and 
            current_time - self.cache_timestamp < self.cache_duration):
            return self.cache[cache_key]

        if not HAS_PYGETWINDOW:
            return []

        all_windows = gw.getAllWindows()
        browser_keywords = ['chrome', 'firefox', 'edge', 'mozilla', 'safari', 'opera', 'brave']

        if browser_type:
            browser_type_lower = browser_type.lower()
            if browser_type_lower == 'firefox':
                browser_keywords = ['firefox', 'mozilla']
            elif browser_type_lower == 'chrome':
                browser_keywords = ['chrome', 'chromium']
            elif browser_type_lower == 'edge':
                browser_keywords = ['edge']

        browser_windows = []
        for window in all_windows:
            if window.title and any(keyword in window.title.lower() for keyword in browser_keywords):
                try:
                    if window.width > 0 and window.height > 0:
                        browser_windows.append(window)
                except Exception:
                    continue

        if self.sort_method == "creation":
            try:
                browser_windows.sort(key=lambda w: w._hWnd if hasattr(w, '_hWnd') else 0)
            except Exception:
                pass
        elif self.sort_method == "position":
            browser_windows.sort(key=lambda w: (w.left, w.top, w.title.lower()))

        self.cache[cache_key] = browser_windows
        self.cache_timestamp = current_time
        return browser_windows

    def select_window(self, browser_config, browser_type=None):
        browser_config = self.normalize_config(browser_config)
        browser_windows = self.get_browser_windows(browser_type, use_cache=True)

        if not browser_windows:
            return None

        method = browser_config.get('window_selection_method', 'auto')

        if method == 'auto':
            return browser_windows[0] if browser_windows else None

        elif method == 'order':
            order = browser_config.get('window_order', 1)
            if 1 <= order <= len(browser_windows):
                return browser_windows[order - 1]
            else:
                return browser_windows[0] if browser_windows else None

        elif method == 'title':
            title_pattern = browser_config.get('window_title_pattern', '')
            if title_pattern:
                for window in browser_windows:
                    try:
                        if re.search(title_pattern, window.title, re.IGNORECASE):
                            return window
                    except re.error:
                        break
            return browser_windows[0] if browser_windows else None

        elif method == 'position':
            target_position = browser_config.get('window_position')
            if target_position and 'x' in target_position and 'y' in target_position:
                target_x, target_y = target_position['x'], target_position['y']
                closest_window = None
                min_distance = float('inf')

                for window in browser_windows:
                    try:
                        distance = ((window.left - target_x) ** 2 + (window.top - target_y) ** 2) ** 0.5
                        if distance < min_distance:
                            min_distance = distance
                            closest_window = window
                    except Exception:
                        continue

                if closest_window:
                    return closest_window

            return browser_windows[0] if browser_windows else None

        elif method == 'manual':
            window_id = browser_config.get('window_id')
            if window_id:
                for window in browser_windows:
                    try:
                        current_id = f"{window.title}_{window.left}_{window.top}_{window.width}_{window.height}"
                        if current_id == window_id:
                            return window
                    except Exception:
                        continue

            return browser_windows[0] if browser_windows else None

        else:
            return browser_windows[0] if browser_windows else None

    def normalize_config(self, browser_config):
        if not browser_config:
            return self.get_default_config()

        if 'window_selection_method' in browser_config:
            return browser_config

        migrated_config = browser_config.copy()
        defaults = {
            'window_selection_method': 'auto',
            'window_order': 1,
            'window_title_pattern': '',
            'window_position': None,
            'window_id': None,
            'window_size': None,
            'remember_window': False
        }
        
        for key, default_value in defaults.items():
            if key not in migrated_config:
                migrated_config[key] = default_value

        return migrated_config

    def get_default_config(self):
        return {
            "type": "Chrome",
            "path": "",
            "url": "",
            "fullscreen": False,
            "window_selection_method": "auto",
            "window_order": 1,
            "window_title_pattern": "",
            "window_position": None,
            "window_id": None,
            "window_size": None,
            "remember_window": False
        }

    def focus_window(self, window):
        if not window:
            return False

        try:
            if not window.isMaximized:
                window.maximize()
                time.sleep(0.5)
            else:
                window.activate()
            return True
        except Exception:
            try:
                pyautogui.hotkey('alt', 'space')
                time.sleep(0.2)
                pyautogui.press('x')
                time.sleep(0.5)
                return True
            except Exception:
                return False

    def clear_cache(self):
        self.cache.clear()
        self.cache_timestamp = 0


class JSExecutor:
    def __init__(self, keyboard_controller, window_manager):
        self.keyboard_controller = keyboard_controller
        self.window_manager = window_manager

    def detect_browser_type(self):
        try:
            if HAS_PYGETWINDOW:
                browser_windows = self.window_manager.get_browser_windows(use_cache=False)
                if browser_windows:
                    title = browser_windows[0].title.lower()
                    if 'firefox' in title:
                        return 'firefox'
                    elif 'edge' in title:
                        return 'edge'
                    else:
                        return 'chrome'
            return 'chrome'
        except Exception:
            return 'chrome'

    def open_console(self, browser_type):
        try:
            if HAS_CONSOLE_SHORTCUTS:
                success = open_console_for_browser(browser_type, self.keyboard_controller)
                if success:
                    random_sleep(0.8, 0.05, 0.15)
                    pyperclip.copy("console.clear();")
                    self.keyboard_controller.hotkey('ctrl', 'v')
                    self.keyboard_controller.press_key('enter')
                    time.sleep(0.2)
                    return True
            
            if browser_type == 'firefox':
                self.keyboard_controller.hotkey('ctrl', 'shift', 'k')
            else:
                self.keyboard_controller.hotkey('ctrl', 'shift', 'j')
            
            time.sleep(0.8)
            pyperclip.copy("console.clear();")
            self.keyboard_controller.hotkey('ctrl', 'v')
            self.keyboard_controller.press_key('enter')
            time.sleep(0.2)
            return True

        except Exception:
            return False

    def close_console(self, browser_type):
        try:
            if HAS_CONSOLE_SHORTCUTS:
                close_console_for_browser(browser_type, self.keyboard_controller)
            else:
                self.keyboard_controller.press_key('f12')
                time.sleep(0.2)
        except Exception:
            pass

    def execute(self, js_code, platform_name, max_wait_time):
        try:
            browser_type = self.detect_browser_type()
            
            if not self.open_console(browser_type):
                time.sleep(max_wait_time)
                return {'detected': False, 'duration': max_wait_time, 'method': 'fallback_timeout'}

            pyperclip.copy(js_code)
            self.keyboard_controller.hotkey('ctrl', 'v')
            
            platform_name_lower = platform_name.lower()
            if 'gemini' in platform_name_lower:
                self.keyboard_controller.hotkey('ctrl', 'enter')
            else:
                self.keyboard_controller.press_key('enter')

            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                self.keyboard_controller.hotkey('ctrl', 'a')
                self.keyboard_controller.hotkey('ctrl', 'c')
                result = pyperclip.paste()

                for line in result.split('\n'):
                    if 'LIRIS_GENERATION_COMPLETE:' in line:
                        try:
                            status = line.split('LIRIS_GENERATION_COMPLETE:')[1].strip().lower()
                            if status == 'true':
                                elapsed = time.time() - start_time
                                self.close_console(browser_type)
                                return {'detected': True, 'duration': elapsed, 'method': 'javascript_detection'}
                        except (IndexError, ValueError):
                            continue

                time.sleep(0.3)

            self.close_console(browser_type)
            elapsed = time.time() - start_time
            return {'detected': False, 'duration': elapsed, 'method': 'timeout'}

        except Exception as e:
            return {'detected': False, 'duration': max_wait_time, 'method': 'error', 'error': str(e)}

    def execute_console_js(self, js_code, browser_type):
        try:
            if not self.open_console(browser_type):
                return False

            pyperclip.copy(js_code)
            self.keyboard_controller.hotkey('ctrl', 'v')
            self.keyboard_controller.press_key('enter')
            time.sleep(0.5)
            time.sleep(0.3)

            result = pyperclip.paste().strip()

            if result and len(result) > 15:
                if not any(keyword in result.lower() for keyword in
                           ['function()', 'console.log', 'document.query', 'let ', 'const ', 'console.clear']):
                    self.close_console(browser_type)
                    return result

            self.close_console(browser_type)
            return False

        except Exception:
            try:
                self.close_console(browser_type)
            except:
                pass
            return False

    def get_detection_script(self, platform_name):
        if 'chatgpt' in platform_name.lower():
            return '''
            (function() {
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

                        if (currentState === lastDataState && currentState.length > 0) {
                            stableCount++;
                            if (stableCount >= 2) {
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
                        return false;
                    }
                }

                checkInterval = setInterval(checkDataStability, 300);
                setTimeout(() => {
                    clearInterval(checkInterval);
                    console.log("LIRIS_GENERATION_COMPLETE:timeout");
                }, 15000);

                return "Detection started";
            })();
            '''
        else:
            return '''
            (function() {
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

                        if (longestText === lastText && longestText.length > 30) {
                            stableCount++;
                            if (stableCount >= 3) {
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
                        return false;
                    }
                }

                checkInterval = setInterval(checkTextStability, 500);
                setTimeout(() => {
                    clearInterval(checkInterval);
                    console.log("LIRIS_GENERATION_COMPLETE:timeout");
                }, 12000);

                return "Generic detection started";
            })();
            '''


class AIConductor:
    def __init__(self, config_provider, scheduler, database=None):
        self.config_provider = config_provider
        self.scheduler = scheduler
        self.database = database

        from core.interaction.mouse import MouseController
        from core.interaction.keyboard import KeyboardController

        self.mouse_controller = MouseController()
        self.keyboard_controller = KeyboardController()

        self.state_automation = StateBasedAutomation(
            None, self.mouse_controller, self.keyboard_controller, self
        )

        self.active_tasks = {}
        self.task_counter = 0
        self.task_queue = queue.Queue()
        self.lock = threading.RLock()
        self._shutdown = False
        self.worker_thread = None

        self.console_timeout = 2
        self.extraction_retries = 2
        self.validation_timeout = 2
        self.browser_already_active = False

        self.browser_manager = BrowserManager()
        self.window_manager = WindowManager()
        self.js_executor = JSExecutor(self.keyboard_controller, self.window_manager)

    def initialize(self):
        try:
            self.worker_thread = threading.Thread(target=self._worker_loop)
            self.worker_thread.daemon = True
            self.worker_thread.start()
            return True
        except Exception as e:
            raise OrchestrationError(f"Init failed: {str(e)}")

    def select_existing_window(self, browser_type='Chrome', window_order=1, platform_name=None, url=None):
        """
        ✅ CORRIGÉ: Méthode correctement indentée dans la classe AIConductor
        Sélectionne une fenêtre existante selon le numéro demandé et ouvre optionnellement une URL
        """
        start_time = time.time()
        
        try:
            # Récupérer window_order depuis la base si pas fourni
            if window_order is None:
                if platform_name and self.database:
                    try:
                        window_info = self.database.get_window_selection_info(platform_name)
                        if window_info:
                            window_order = window_info.get('order', 1)
                            logger.info(f"Window order from database for {platform_name}: {window_order}")
                        else:
                            window_order = 1
                            logger.info(f"No window config found for {platform_name}, using default: 1")
                    except Exception as e:
                        logger.warning(f"Error getting window config from database: {e}")
                        window_order = 1
                else:
                    window_order = 1
                    logger.info("No platform_name provided, using default window_order: 1")
            else:
                logger.info(f"Using provided window_order: {window_order}")
                
            logger.info(f"Selecting existing {browser_type} window #{window_order}")
            
            # Lister les fenêtres existantes
            self.window_manager.clear_cache()
            existing_windows = self.window_manager.get_browser_windows(browser_type, use_cache=False)
            logger.info(f"Found {len(existing_windows)} existing {browser_type} windows")
            
            if not existing_windows:
                return {
                    'success': False,
                    'message': f"No {browser_type} windows found",
                    'duration': time.time() - start_time,
                    'available_windows': 0,
                    'requested_order': window_order
                }
            
            # Vérifier si le numéro demandé existe
            if window_order > len(existing_windows):
                return {
                    'success': False,
                    'message': f"Window #{window_order} not found. Only {len(existing_windows)} windows available",
                    'duration': time.time() - start_time,
                    'available_windows': len(existing_windows),
                    'requested_order': window_order
                }
            
            # Sélectionner la fenêtre demandée (index 0-based)
            target_window = existing_windows[window_order - 1]
            
            # Focus/maximiser la fenêtre
            focus_success = self.window_manager.focus_window(target_window)
            
            # ✅ NOUVEAU: Ouvrir l'URL si fournie
            url_opened = False
            if url and url.strip():
                logger.info(f"Opening URL in selected window: {url}")
                try:
                    # Ouvrir l'URL dans un nouvel onglet
                    result = self.browser_manager.open_url(url, browser_type, new_window=False)
                    if result.get('success'):
                        url_opened = True
                        logger.info(f"URL opened successfully in window #{window_order}")
                        time.sleep(1)  # Laisser le temps à l'onglet de s'ouvrir
                    else:
                        logger.warning(f"Failed to open URL: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.warning(f"Error opening URL: {e}")
            
            total_duration = time.time() - start_time
            
            return {
                'success': True,
                'message': f"{browser_type} window #{window_order} selected successfully" + 
                          (f" and URL opened" if url_opened else ""),
                'duration': total_duration,
                'browser_type': browser_type,
                'window_order': window_order,
                'platform_name': platform_name,
                'url_opened': url_opened,  # ✅ Nouveau champ
                'selected_window': {
                    'title': target_window.title,
                    'position': {'x': target_window.left, 'y': target_window.top},
                    'size': {'width': target_window.width, 'height': target_window.height},
                    'focused': focus_success
                },
                'total_windows': len(existing_windows),
                'config_source': 'database' if platform_name and window_order != 1 else 'default',
                'method': 'existing_window_selection'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Error selecting window: {str(e)}",
                'duration': time.time() - start_time
            }

            
    def open_browser_only(self, browser_type='Chrome', url='', window_order=None, new_window=True, platform_name=None):
        """
        Ouvre simplement le navigateur et sélectionne la fenêtre demandée
        
        Args:
            browser_type (str): Type de navigateur ('Chrome', 'Firefox', 'Edge')
            url (str): URL à ouvrir
            window_order (int, optional): Numéro de la fenêtre à sélectionner - si None, récupère depuis la base
            new_window (bool): Forcer nouvelle fenêtre ou pas
            platform_name (str, optional): Nom de plateforme pour récupérer config depuis base
            
        Returns:
            dict: Résultat avec infos de la fenêtre sélectionnée
        """
        start_time = time.time()
        
        try:
            if not url:
                url = "about:blank"

            # Récupérer window_order depuis la base si pas fourni
            if window_order is None:
                if platform_name and self.database:
                    try:
                        window_info = self.database.get_window_selection_info(platform_name)
                        if window_info:
                            window_order = window_info.get('order', 1)
                            logger.info(f"Window order from database for {platform_name}: {window_order}")
                        else:
                            window_order = 1
                            logger.info(f"No window config found for {platform_name}, using default: 1")
                    except Exception as e:
                        logger.warning(f"Error getting window config from database: {e}")
                        window_order = 1
                else:
                    window_order = 1
                    logger.info("No platform_name provided, using default window_order: 1")
            else:
                logger.info(f"Using provided window_order: {window_order}")
                
            logger.info(f"Opening browser {browser_type} with window #{window_order}")
            
            # Lister fenêtres avant ouverture
            self.window_manager.clear_cache()
            windows_before = self.window_manager.get_browser_windows(browser_type, use_cache=False)
            logger.info(f"Windows before: {len(windows_before)}")
            
            # Ouvrir navigateur
            result = self.browser_manager.open_url(url, browser_type, new_window=new_window)
            
            if not result.get('success'):
                return {
                    'success': False,
                    'message': f"Failed to open {browser_type}: {result.get('error', 'Unknown error')}",
                    'duration': time.time() - start_time
                }
            
            # Attendre que le navigateur se lance
            time.sleep(3)
            
            # Lister fenêtres après ouverture
            self.window_manager.clear_cache()
            windows_after = self.window_manager.get_browser_windows(browser_type, use_cache=False)
            logger.info(f"Windows after: {len(windows_after)}")
            
            # Sélectionner la fenêtre demandée
            target_window = self.select_window_intelligently(
                windows_before, windows_after, window_order, url, browser_type
            )
            
            if not target_window:
                return {
                    'success': False,
                    'message': f"No window found for order #{window_order}",
                    'duration': time.time() - start_time,
                    'available_windows': len(windows_after),
                    'requested_order': window_order
                }
            
            # Focus/maximiser la fenêtre
            focus_success = self.window_manager.focus_window(target_window)
            
            total_duration = time.time() - start_time
            
            return {
                'success': True,
                'message': f"Browser {browser_type} opened and window #{window_order} selected",
                'duration': total_duration,
                'browser_type': browser_type,
                'window_order': window_order,
                'platform_name': platform_name,
                'selected_window': {
                    'title': target_window.title,
                    'position': {'x': target_window.left, 'y': target_window.top},
                    'size': {'width': target_window.width, 'height': target_window.height},
                    'focused': focus_success
                },
                'method': result.get('method', 'unknown'),
                'total_windows': len(windows_after),
                'config_source': 'database' if platform_name and window_order != 1 else 'default'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f"Error opening browser: {str(e)}",
                'duration': time.time() - start_time
            }

    def test_browser_only(self, platform_name, browser_type='Chrome', browser_path='', url='', window_order=1):
        start_time = time.time()
        test_id = f"browser_test_{platform_name}_{int(start_time)}"

        try:
            self.window_manager.clear_cache()
            windows_before = self.window_manager.get_browser_windows(browser_type, use_cache=False)

            result = self.browser_manager.open_url(url, browser_type, new_window=True)
            
            if result.get('success'):
                time.sleep(3)
                
                self.window_manager.clear_cache()
                windows_after = self.window_manager.get_browser_windows(browser_type, use_cache=False)
                
                target_window = self.select_window_intelligently(
                    windows_before, windows_after, window_order, url, browser_type
                )
                
                if target_window:
                    self.window_manager.focus_window(target_window)
                    
                    total_duration = time.time() - start_time
                    
                    return {
                        'success': True,
                        'message': f"Browser {browser_type} opened successfully",
                        'duration': total_duration,
                        'test_id': test_id,
                        'method': result.get('method', 'unknown'),
                        'browser_type': browser_type,
                        'window_order': window_order,
                        'selected_window': target_window.title
                    }
                else:
                    return {
                        'success': False,
                        'message': f"No window found for #{window_order}",
                        'duration': time.time() - start_time,
                        'test_id': test_id
                    }
            
            else:
                return {
                    'success': False,
                    'message': f"Browser open error: {result.get('error', 'Unknown')}",
                    'duration': time.time() - start_time,
                    'test_id': test_id
                }

        except Exception as e:
            return {
                'success': False,
                'message': f"Error: {str(e)}",
                'duration': time.time() - start_time,
                'test_id': test_id
            }

    def select_window_intelligently(self, windows_before, windows_after, window_order, target_url, browser_type):
        try:
            if not windows_after:
                return None

            handles_before = {w._hWnd for w in windows_before if hasattr(w, '_hWnd')}
            new_windows = [w for w in windows_after if hasattr(w, '_hWnd') and w._hWnd not in handles_before]

            if new_windows:
                return new_windows[0]
            else:
                if 1 <= window_order <= len(windows_after):
                    return windows_after[window_order - 1]
                else:
                    return windows_after[-1] if windows_after else None
                
        except Exception:
            return windows_after[0] if windows_after else None

    def test_platform(self, platform_name, test_message="Test", timeout=30, wait_for_response=12, 
                     skip_browser=True, window_selection_method=None, window_order=None,
                     window_title_pattern=None, window_position=None, window_id=None, **kwargs):
        start_time = time.time()
        test_id = f"test_{platform_name}_{int(start_time)}"

        try:
            self.window_manager.clear_cache()

            config_result = self.validate_platform_config(platform_name)
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

            if window_selection_method is not None:
                browser_config['window_selection_method'] = window_selection_method
            if window_order is not None:
                browser_config['window_order'] = window_order
            if window_title_pattern is not None:
                browser_config['window_title_pattern'] = window_title_pattern
            if window_position is not None:
                browser_config['window_position'] = window_position
            if window_id is not None:
                browser_config['window_id'] = window_id

            browser_config = self.window_manager.normalize_config(browser_config)
            browser_type = self.detect_browser_type_from_profile(profile)

            if hasattr(self.state_automation, 'browser_type'):
                self.state_automation.browser_type = browser_type

            if not skip_browser:
                browser_result = self.open_browser(browser_type, browser_config.get('path', ''), 
                                                 browser_config.get('url'), browser_config, platform_name, True)
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
                self.focus_existing_browser(browser_config, platform_name)

            automation_params = {
                'test_text': test_message,
                'skip_browser_activation': True
            }

            automation_result = self.run_automation(profile, automation_params, timeout, browser_type)
            if not automation_result['success']:
                return {
                    'success': False,
                    'error': 'automation_failed',
                    'message': automation_result['message'],
                    'test_id': test_id,
                    'duration': time.time() - start_time
                }

            total_duration = time.time() - start_time
            response_text = automation_result.get('response', '')

            return {
                'success': True,
                'message': f"Test successful in {total_duration:.1f}s",
                'response': response_text,
                'test_id': test_id,
                'duration': total_duration,
                'metadata': {
                    'automation_duration': automation_result.get('duration', 0),
                    'response_length': len(response_text),
                    'extraction_method': 'state_automation_internal',
                    'browser_skipped': skip_browser,
                    'browser_type': browser_type,
                    'window_selection_method': browser_config.get('window_selection_method', 'auto'),
                    'window_order': browser_config.get('window_order', 1),
                    'sort_method': self.window_manager.sort_method
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': 'unexpected_error',
                'message': str(e),
                'test_id': test_id,
                'duration': time.time() - start_time
            }

    def wait_for_ai_response(self, platform_name, max_wait_time):
        js_code = self.js_executor.get_detection_script(platform_name)
        return self.js_executor.execute(js_code, platform_name, max_wait_time)

    def detect_browser_type_from_profile(self, profile):
        try:
            browser_config = profile.get('browser', {})
            browser_config = self.window_manager.normalize_config(browser_config)

            browser_type = browser_config.get('type', '').lower()
            browser_path = browser_config.get('path', '').lower()

            if browser_type:
                if 'firefox' in browser_type:
                    return 'firefox'
                elif 'chrome' in browser_type:
                    return 'chrome'
                elif 'edge' in browser_type:
                    return 'edge'

            if browser_path:
                if 'firefox' in browser_path:
                    return 'firefox'
                elif 'chrome' in browser_path:
                    return 'chrome'
                elif 'edge' in browser_path:
                    return 'edge'

            return 'chrome'

        except Exception:
            return 'chrome'

    def validate_platform_config(self, platform_name):
        try:
            profile = self.get_platform_profile(platform_name)
            if not profile:
                return {
                    'valid': False,
                    'message': f"Profile {platform_name} not found",
                    'profile': None
                }

            if 'browser' in profile:
                profile['browser'] = self.window_manager.normalize_config(profile['browser'])

            missing_elements = []
            browser_config = profile.get('browser', {})
            if not browser_config.get('url'):
                missing_elements.append('Browser URL')

            interface_positions = profile.get('interface_positions', {})
            if not interface_positions.get('prompt_field'):
                missing_elements.append('Prompt field position')

            if missing_elements:
                return {
                    'valid': False,
                    'message': f"Missing elements: {', '.join(missing_elements)}",
                    'profile': profile
                }

            return {
                'valid': True,
                'message': "Configuration complete",
                'profile': profile
            }

        except Exception as e:
            return {
                'valid': False,
                'message': f"Validation error: {str(e)}",
                'profile': None
            }

    def get_platform_profile(self, platform_name):
        try:
            profiles = self.config_provider.get_profiles()
            memory_profile = profiles.get(platform_name)

            if memory_profile:
                if 'browser' in memory_profile:
                    memory_profile['browser'] = self.window_manager.normalize_config(memory_profile['browser'])
                return memory_profile

            if self.database and hasattr(self.database, 'get_platform'):
                db_profile = self.database.get_platform(platform_name)
                if db_profile:
                    if 'browser' in db_profile:
                        db_profile['browser'] = self.window_manager.normalize_config(db_profile['browser'])
                    return db_profile

            return None

        except Exception as e:
            return None

    def open_browser(self, browser_type, browser_path='', url='', browser_config=None, platform_name=None, fullscreen=False):
        try:
            if not url:
                url = "about:blank"

            if browser_config:
                browser_config = self.window_manager.normalize_config(browser_config)

            if hasattr(self, 'browser_manager'):
                result = self.browser_manager.open_url(url, browser_type)
                if result.get('success'):
                    time.sleep(3)
                    if fullscreen:
                        self.maximize_selected_window(browser_config, browser_type, platform_name)
                    
                    elapsed = 3
                    self.browser_already_active = True
                    
                    return {
                        'success': True,
                        'message': f"Browser activated in {elapsed:.1f}s",
                        'duration': elapsed
                    }

            if browser_type.lower() == "firefox":
                cmd = f'start firefox "{url}"'
            elif browser_type.lower() == "chrome":
                cmd = f'start chrome "{url}"'
            elif browser_type.lower() == "edge":
                cmd = f'start msedge "{url}"'
            else:
                cmd = f'start "{browser_path}" "{url}"' if browser_path else f'start "{url}"'

            start_time = time.time()
            os.system(cmd)
            time.sleep(3)

            if fullscreen:
                time.sleep(1)
                self.window_manager.clear_cache()
                self.maximize_selected_window(browser_config, browser_type, platform_name)

            elapsed = time.time() - start_time
            self.browser_already_active = True

            return {
                'success': True,
                'message': f"Browser activated in {elapsed:.1f}s",
                'duration': elapsed
            }

        except Exception as e:
            return {
                'success': False,
                'message': f"Activation error: {str(e)}",
                'duration': 0
            }

    def focus_existing_browser(self, browser_config, platform_name=None):
        browser_found = False
        platform_url = browser_config.get('url', '')

        browser_config = self.window_manager.normalize_config(browser_config)
        self.window_manager.clear_cache()

        if HAS_PYGETWINDOW:
            try:
                browser_type = browser_config.get('type', 'Chrome')
                target_window = self.window_manager.select_window(browser_config, browser_type)

                if target_window:
                    browser_found = True
                    self.browser_already_active = True

                    try:
                        if not target_window.isMaximized:
                            target_window.maximize()

                        if platform_name:
                            self.remember_window_selection(platform_name, target_window, browser_config)

                    except Exception:
                        pass

            except Exception:
                pass

        if browser_found and platform_url:
            
            if hasattr(self, 'browser_manager') and self.browser_manager.can_open():
                result = self.browser_manager.open_url(platform_url, browser_config.get('type', 'Chrome'))
                if result.get('success'):
                    random_sleep(1.5, 0.10, 0.20)
                    self.window_manager.clear_cache()
                    return
            
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
                random_sleep(1.5, 0.10, 0.20)
                self.window_manager.clear_cache()
                
            except Exception:
                pass

    def maximize_selected_window(self, browser_config=None, browser_type=None, platform_name=None):
        try:
            if browser_config:
                browser_config = self.window_manager.normalize_config(browser_config)
                target_window = self.window_manager.select_window(browser_config, browser_type)

                if target_window:
                    if not target_window.isMaximized:
                        target_window.maximize()
                        time.sleep(0.5)
                    else:
                        target_window.activate()

                    if platform_name:
                        self.remember_window_selection(platform_name, target_window, browser_config)

                    return True

            return self.window_manager.focus_window(None)

        except Exception:
            return self.window_manager.focus_window(None)

    def run_automation(self, profile, automation_params, timeout, browser_type='chrome'):
        try:
            automation_result = None
            automation_start = time.time()

            def on_automation_completed(success, message, duration, response):
                nonlocal automation_result
                automation_result = {
                    'success': success,
                    'message': message,
                    'duration': duration,
                    'response': response
                }

            self.state_automation.automation_completed.connect(on_automation_completed)

            browser_config = profile.get('browser', {})
            if automation_params is None:
                automation_params = {}

            self.state_automation.start_test_automation(
                profile, 0, browser_type,
                browser_config.get('url'), automation_params
            )

            automation_timeout = min(25, timeout - 5)
            while automation_result is None and (time.time() - automation_start) < automation_timeout:
                time.sleep(0.1)

            try:
                self.state_automation.automation_completed.disconnect(on_automation_completed)
            except:
                pass

            if automation_result is None:
                return {
                    'success': False,
                    'message': f"Automation timeout ({automation_timeout}s)",
                    'duration': time.time() - automation_start,
                    'response': ''
                }

            return automation_result

        except Exception as e:
            return {
                'success': False,
                'message': f"Automation error: {str(e)}",
                'duration': time.time() - automation_start if 'automation_start' in locals() else 0,
                'response': ''
            }

    def remember_window_selection(self, platform_name, window, browser_config):
        try:
            if not browser_config.get('remember_window', False):
                return

            if not window:
                return

            window_id = f"{window.title}_{window.left}_{window.top}_{window.width}_{window.height}"
            browser_config['window_id'] = window_id
            browser_config['window_selection_method'] = 'manual'

            try:
                if self.database and hasattr(self.database, 'update_window_selection'):
                    self.database.update_window_selection(platform_name, {
                        'method': 'manual',
                        'window_id': window_id
                    })
            except Exception:
                pass

        except Exception:
            pass

    def get_browser_windows_info(self, browser_type=None):
        try:
            self.window_manager.clear_cache()
            windows = self.window_manager.get_browser_windows(browser_type, use_cache=False)
            windows_info = []

            for i, window in enumerate(windows, 1):
                try:
                    window_info = {
                        'order': i,
                        'title': window.title,
                        'position': {'x': window.left, 'y': window.top},
                        'size': {'width': window.width, 'height': window.height},
                        'is_maximized': window.isMaximized,
                        'window_id': f"{window.title}_{window.left}_{window.top}_{window.width}_{window.height}",
                        'sort_method': self.window_manager.sort_method
                    }
                    if hasattr(window, '_hWnd'):
                        window_info['handle'] = window._hWnd
                    windows_info.append(window_info)
                except Exception:
                    continue

            return windows_info

        except Exception:
            return []

    def test_window_selection(self, platform_name, window_selection_config):
        try:
            self.window_manager.clear_cache()
            browser_config = self.window_manager.get_default_config()
            browser_config.update(window_selection_config)

            selected_window = self.window_manager.select_window(
                browser_config,
                browser_config.get('type', 'Chrome')
            )

            if selected_window:
                result_info = {
                    'title': selected_window.title,
                    'position': {'x': selected_window.left, 'y': selected_window.top},
                    'size': {'width': selected_window.width, 'height': selected_window.height},
                    'sort_method': self.window_manager.sort_method
                }
                if hasattr(selected_window, '_hWnd'):
                    result_info['handle'] = selected_window._hWnd
                    
                return {
                    'success': True,
                    'selected_window': result_info,
                    'message': f"Window selected: {selected_window.title}"
                }
            else:
                return {
                    'success': False,
                    'selected_window': None,
                    'message': f"No window found with these criteria"
                }

        except Exception as e:
            return {
                'success': False,
                'selected_window': None,
                'message': f"Error: {str(e)}"
            }

    def get_available_platforms(self):
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
        except Exception:
            return []

    def shutdown(self):
        try:
            self._shutdown = True
            if hasattr(self.state_automation, 'stop_automation'):
                self.state_automation.stop_automation()
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=2)
        except Exception:
            pass

    def emergency_stop(self):
        try:
            self._shutdown = True
            if hasattr(self.state_automation, 'stop_automation'):
                self.state_automation.stop_automation()
            try:
                self.keyboard_controller.press_key('f12')
            except:
                pass
        except Exception:
            pass

    def _worker_loop(self):
        while not self._shutdown:
            try:
                time.sleep(1)
            except Exception:
                break

    def send_prompt(self, platform, prompt, mode="standard", priority=0, sync=False, timeout=None):
        try:
            can_use, reason = self.scheduler.can_use_platform(platform)
            if not can_use:
                raise SchedulingError(reason)

            if sync:
                result = self.test_platform(platform, prompt, timeout or 30, 12)

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

            raise NotImplementedError("Async mode not implemented")

        except Exception as e:
            raise OrchestrationError(f"Send failed: {str(e)}")

    def detect_platform_elements(self, platform_name, browser_type='Chrome', browser_path='', url='', fullscreen=False):
        return {
            'success': False,
            'error': 'not_implemented',
            'message': "Element detection not implemented"
        }

    def test_platform_connection(self, platform_name, **kwargs):
        return self.test_platform(platform_name, **kwargs)