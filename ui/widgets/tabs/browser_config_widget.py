#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ui/widgets/tabs/browser_config_widget.py - VERSION CORRIGÉE
"""

import os
import json
import time
import traceback
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from config.detect_clic_user import detect_window_click, save_window_position, get_window_position


class BrowserConfigWidget(QtWidgets.QWidget):
    browser_saved = pyqtSignal(str, dict)
    browser_deleted = pyqtSignal(str)
    browser_used = pyqtSignal(str, str)
    elements_detected = pyqtSignal(str, dict)
    window_selection_changed = pyqtSignal(str, dict)

    def __init__(self, config_provider, conductor, parent=None):
        super().__init__(parent)

        self.config_provider = config_provider
        self.conductor = conductor
        self.profiles = {}
        self.database = getattr(conductor, 'database', None)
        self.click_detection_running = False

        try:
            self._init_ui()
        except Exception as e:
            logger.error(f"Error initializing BrowserConfigWidget: {str(e)}")

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        explanation = QtWidgets.QLabel(
            "Configure browser window selection for AI platforms.\n"
            "Select your platform, enter the URL, then click on the browser window you want to use."
        )
        explanation.setStyleSheet(PlatformConfigStyle.get_explanation_style())
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(explanation)

        main_form_group = QtWidgets.QGroupBox("Platform Configuration")
        main_form_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        main_form = QtWidgets.QFormLayout(main_form_group)
        main_form.setSpacing(15)

        self.browser_platform_combo = QtWidgets.QComboBox()
        self.browser_platform_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.browser_platform_combo.currentIndexChanged.connect(self._on_platform_selected)
        main_form.addRow("Platform:", self.browser_platform_combo)

        self.browser_type_combo = QtWidgets.QComboBox()
        self.browser_type_combo.addItems(["Chrome", "Firefox", "Edge"])
        self.browser_type_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        main_form.addRow("Browser Type:", self.browser_type_combo)

        self.browser_url_edit = QtWidgets.QLineEdit()
        self.browser_url_edit.setPlaceholderText("Platform URL (e.g., https://chat.openai.com)")
        self.browser_url_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        main_form.addRow("Platform URL:", self.browser_url_edit)

        main_layout.addWidget(main_form_group)

        steps_group = QtWidgets.QGroupBox("Setup Steps")
        steps_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        steps_layout = QtWidgets.QVBoxLayout(steps_group)

        step1_layout = QtWidgets.QHBoxLayout()
        step1_label = QtWidgets.QLabel("1. Setup Window Position:")
        step1_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.detect_click_button = QtWidgets.QPushButton("📍 Click to Select Window")
        self.detect_click_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.detect_click_button.clicked.connect(self._start_click_detection)
        step1_layout.addWidget(step1_label)
        step1_layout.addStretch()
        step1_layout.addWidget(self.detect_click_button)
        steps_layout.addLayout(step1_layout)

        self.click_status = QtWidgets.QLabel("No window position configured")
        self.click_status.setAlignment(Qt.AlignCenter)
        self.click_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        steps_layout.addWidget(self.click_status)

        step2_layout = QtWidgets.QHBoxLayout()
        step2_label = QtWidgets.QLabel("2. Test Configuration:")
        step2_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.test_browser_button = QtWidgets.QPushButton("🧪 Test Browser Setup")
        self.test_browser_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.test_browser_button.clicked.connect(self._test_browser)
        self.test_browser_button.setEnabled(False)
        step2_layout.addWidget(step2_label)
        step2_layout.addStretch()
        step2_layout.addWidget(self.test_browser_button)
        steps_layout.addLayout(step2_layout)

        self.test_status = QtWidgets.QLabel("No test performed")
        self.test_status.setAlignment(Qt.AlignCenter)
        self.test_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        steps_layout.addWidget(self.test_status)

        main_layout.addWidget(steps_group)

        save_layout = QtWidgets.QHBoxLayout()
        save_layout.addStretch()
        self.save_config_button = QtWidgets.QPushButton("💾 Save Configuration")
        self.save_config_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_config_button.clicked.connect(self._save_configuration)
        self.save_config_button.setEnabled(False)
        save_layout.addWidget(self.save_config_button)
        save_layout.addStretch()
        main_layout.addLayout(save_layout)

        info_group = QtWidgets.QGroupBox("How It Works")
        info_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        info_layout = QtWidgets.QVBoxLayout(info_group)

        info_text = QtWidgets.QLabel(
            "🎯 <b>Window Selection Process:</b>\n\n"
            "1. Select your platform and enter the URL\n"
            "2. Open your browser and navigate to the platform\n"
            "3. Click 'Click to Select Window' and then click on the browser window\n"
            "4. Test the configuration to verify it works\n"
            "5. Save the configuration\n\n"
            "💡 <b>During tests:</b> The system will click on the saved position to activate your window and open the URL."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: #555; padding: 15px; background-color: #f8f9fa; border-radius: 8px; line-height: 1.4;")
        info_layout.addWidget(info_text)

        main_layout.addWidget(info_group)
        main_layout.addStretch()

    def set_profiles(self, profiles):
        self.profiles = profiles
        self._update_platforms_combo()

    def select_platform(self, platform_name):
        index = self.browser_platform_combo.findText(platform_name)
        if index >= 0:
            self.browser_platform_combo.setCurrentIndex(index)

    def refresh(self):
        self._update_platforms_combo()

    def _update_platforms_combo(self):
        current_text = self.browser_platform_combo.currentText()

        self.browser_platform_combo.clear()
        self.browser_platform_combo.addItem("-- Select a platform --")

        for name in sorted(self.profiles.keys()):
            self.browser_platform_combo.addItem(name)

        if current_text:
            index = self.browser_platform_combo.findText(current_text)
            if index >= 0:
                self.browser_platform_combo.setCurrentIndex(index)

    def _on_platform_selected(self, index):
        if index <= 0:
            self._reset_ui()
            return

        platform_name = self.browser_platform_combo.currentText()
        profile = self.profiles.get(platform_name, {})
        browser_info = profile.get('browser', {})

        browser_type = browser_info.get('type', 'Chrome')
        type_index = self.browser_type_combo.findText(browser_type)
        if type_index >= 0:
            self.browser_type_combo.setCurrentIndex(type_index)

        self.browser_url_edit.setText(browser_info.get('url', ''))

        window_position = profile.get('window_position')
        if window_position and 'x' in window_position and 'y' in window_position:
            self.click_status.setText(f"Window position: ({window_position['x']}, {window_position['y']})")
            self.click_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
            self.test_browser_button.setEnabled(True)
        else:
            self.click_status.setText("No window position configured")
            self.click_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
            self.test_browser_button.setEnabled(False)

        if 'interface_positions' in profile:
            self.test_status.setText("Interface positions configured")
            self.test_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
            self.save_config_button.setEnabled(True)
        else:
            self.test_status.setText("No test performed")
            self.test_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
            self.save_config_button.setEnabled(False)

    def _reset_ui(self):
        self.click_status.setText("No window position configured")
        self.click_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.test_status.setText("No test performed")
        self.test_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.test_browser_button.setEnabled(False)
        self.save_config_button.setEnabled(False)
        self.browser_url_edit.clear()

    def _sync_profile_to_config_provider(self, platform_name, profile):
        """Synchronise le profil avec le config_provider du conductor pour éviter les désynchronisations"""
        try:
            # Mettre à jour dans le widget
            self.profiles[platform_name] = profile
            
            # Mettre à jour dans le config_provider si disponible
            if hasattr(self.config_provider, 'profiles'):
                self.config_provider.profiles[platform_name] = profile
            elif hasattr(self.config_provider, 'set_profile'):
                self.config_provider.set_profile(platform_name, profile)
            elif hasattr(self.config_provider, '_profiles'):
                self.config_provider._profiles[platform_name] = profile
            
            logger.debug(f"Profile synchronized for {platform_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error synchronizing profile for {platform_name}: {str(e)}")
            return False

    def _start_click_detection(self):
        platform_index = self.browser_platform_combo.currentIndex()
        if platform_index <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                "No platform selected",
                "Please select a platform first."
            )
            return

        url = self.browser_url_edit.text().strip()
        if not url:
            QtWidgets.QMessageBox.warning(
                self,
                "URL missing",
                "Please enter the platform URL first."
            )
            return

        platform_name = self.browser_platform_combo.currentText()

        QtWidgets.QMessageBox.information(
            self,
            "Click Detection",
            f"Setup for {platform_name}:\n\n"
            f"1. Make sure your browser is open with {platform_name}\n"
            f"2. Click OK to start detection\n"
            f"3. Click anywhere on the {platform_name} browser window\n\n"
            f"You have 30 seconds to click on the window."
        )

        self.click_detection_running = True
        self.detect_click_button.setText("⏳ Click on browser window...")
        self.detect_click_button.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        try:
            position = detect_window_click(timeout=30)
            
            if position:
                logger.info(f"Position detected: {position}")
                
                # Récupérer le profil existant ou créer un nouveau
                profile = self.profiles.get(platform_name, {})
                profile['window_position'] = position
                
                if self.database:
                    # Sauvegarder en base de données
                    save_success = self.database.save_platform(platform_name, profile)
                    if save_success:
                        # Synchroniser avec le config_provider
                        sync_success = self._sync_profile_to_config_provider(platform_name, profile)
                        
                        if sync_success:
                            self.click_status.setText(f"Window position: ({position['x']}, {position['y']})")
                            self.click_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
                            self.test_browser_button.setEnabled(True)
                            
                            logger.info(f"Window position saved and synchronized for {platform_name}: {position}")
                            
                            QtWidgets.QMessageBox.information(
                                self,
                                "Position Saved",
                                f"Window position saved: ({position['x']}, {position['y']})\n\n"
                                f"You can now test the configuration."
                            )
                        else:
                            QtWidgets.QMessageBox.warning(
                                self,
                                "Sync Warning",
                                "Position saved to database but sync with conductor failed.\nTry restarting the application."
                            )
                    else:
                        QtWidgets.QMessageBox.critical(
                            self,
                            "Save Error",
                            "Failed to save window position to database."
                        )
                else:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Database Error",
                        "Database not available for saving position."
                    )
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Detection Failed",
                    "No click detected within 30 seconds.\nPlease try again."
                )

        except Exception as e:
            logger.error(f"Error during click detection: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Detection Error",
                f"An error occurred during click detection:\n{str(e)}"
            )

        finally:
            self.click_detection_running = False
            self.detect_click_button.setText("📍 Click to Select Window")
            self.detect_click_button.setEnabled(True)

    def _test_browser(self):
        platform_index = self.browser_platform_combo.currentIndex()
        if platform_index <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                "No platform selected",
                "Please select a platform first."
            )
            return

        platform_name = self.browser_platform_combo.currentText()
        browser_type = self.browser_type_combo.currentText()
        browser_url = self.browser_url_edit.text().strip()

        if not browser_url:
            QtWidgets.QMessageBox.warning(
                self,
                "URL missing",
                "Please enter the platform URL."
            )
            return

        # Vérifier que les coordonnées sont bien sauvegardées
        profile = self.profiles.get(platform_name, {})
        window_position = profile.get('window_position')
        
        if not window_position or 'x' not in window_position or 'y' not in window_position:
            QtWidgets.QMessageBox.warning(
                self,
                "No Window Position",
                "Please click 'Click to Select Window' first to save a window position."
            )
            return

        # S'assurer que le conductor a bien les coordonnées - forcer la synchronisation
        logger.info(f"Testing browser for {platform_name} with position {window_position}")
        
        # Vérifier que le conductor peut récupérer les coordonnées
        conductor_profile = self.conductor.get_platform_profile(platform_name)
        conductor_position = conductor_profile.get('window_position') if conductor_profile else None
        
        logger.info(f"Conductor profile position: {conductor_position}")
        
        if not conductor_position:
            # Forcer la synchronisation
            logger.warning("Conductor doesn't have the position, forcing sync...")
            self._sync_profile_to_config_provider(platform_name, profile)
            
            # Revérifier
            conductor_profile = self.conductor.get_platform_profile(platform_name)
            conductor_position = conductor_profile.get('window_position') if conductor_profile else None
            
            if not conductor_position:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Sync Error",
                    "Could not synchronize window position with conductor.\nPlease try saving the position again."
                )
                return

        # Important warning before test
        reply = QtWidgets.QMessageBox.information(
            self,
            "Test Starting",
            f"🚨 <b>IMPORTANT:</b>\n\n"
            f"The test will now automatically:\n"
            f"• Click on saved position: ({window_position['x']}, {window_position['y']})\n"
            f"• Navigate to the platform URL in that window\n\n"
            f"⚠️ <b>Make sure your browser window is open and visible!</b>\n"
            f"⚠️ <b>DO NOT TOUCH YOUR MOUSE OR KEYBOARD</b> during the test!\n\n"
            f"The test will take about 3-4 seconds.\n"
            f"Ready to start?",
            QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Ok
        )
        
        if reply != QtWidgets.QMessageBox.Ok:
            return

        self.test_status.setText("Testing...")
        self.test_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        QtWidgets.QApplication.processEvents()

        try:
            progress = QtWidgets.QProgressDialog(
                f"Testing browser setup for {platform_name}...\n\nDO NOT TOUCH MOUSE OR KEYBOARD!",
                "Cancel",
                0, 100,
                self
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setValue(10)

            progress.setLabelText(f"Step 1/2: Clicking on saved position ({window_position['x']}, {window_position['y']})...")
            progress.setValue(30)
            QtWidgets.QApplication.processEvents()

            result = self.conductor.select_existing_window(
                browser_type=browser_type,
                platform_name=platform_name,
                url=browser_url
            )

            progress.setValue(70)
            progress.setLabelText("Step 2/2: Navigating to URL in activated window...")
            QtWidgets.QApplication.processEvents()

            time.sleep(1)  # Let URL navigation complete
            progress.setValue(100)

            if result.get('success'):
                self.test_status.setText("Test successful!")
                self.test_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

                duration = result.get('duration', 0)
                method = result.get('method', 'unknown')

                success_message = (
                    f"Browser setup test successful for {platform_name}!\n\n"
                    f"✅ Clicked on saved position: ({window_position['x']}, {window_position['y']})\n"
                    f"✅ Window activated successfully\n"
                    f"✅ Platform URL opened: {browser_url}\n"
                    f"⏱️ Test completed in {duration:.1f}s\n"
                    f"🔧 Method: {method}\n\n"
                    f"The browser configuration is working correctly.\n"
                    f"You can now proceed to configure interface elements.\n\n"
                    f"You can now safely use your mouse and keyboard again."
                )

                QtWidgets.QMessageBox.information(
                    self,
                    "Test Successful",
                    success_message
                )

                self._save_browser_config(platform_name, browser_type, browser_url)

            else:
                progress.cancel()
                error_msg = result.get('message', 'Unknown error')
                
                self.test_status.setText("Test failed!")
                self.test_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())

                QtWidgets.QMessageBox.critical(
                    self,
                    "Test Failed",
                    f"Browser test failed: {error_msg}\n\n"
                    f"Possible solutions:\n"
                    f"• Make sure the browser window is open and visible\n"
                    f"• Try detecting the window position again\n"
                    f"• Check that the URL is correct\n"
                    f"• Ensure the saved position ({window_position['x']}, {window_position['y']}) is still valid\n\n"
                    f"You can now safely use your mouse and keyboard again."
                )

        except Exception as e:
            logger.error(f"Error during test: {str(e)}")
            self.test_status.setText("Test error!")
            self.test_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())

            QtWidgets.QMessageBox.critical(
                self,
                "Test Error",
                f"An error occurred during testing:\n{str(e)}\n\n"
                f"You can now safely use your mouse and keyboard again."
            )

    def _save_browser_config(self, platform_name, browser_type, browser_url):
        try:
            profile = self.profiles.get(platform_name, {})

            browser_config = {
                "type": browser_type,
                "url": browser_url,
                "path": "",
                "fullscreen": False
            }

            if 'browser' not in profile:
                profile['browser'] = {}
            profile['browser'].update(browser_config)

            if self.database:
                save_success = self.database.save_platform(platform_name, profile)
                if save_success:
                    # Synchroniser avec le config_provider
                    self._sync_profile_to_config_provider(platform_name, profile)
                    
                    logger.info(f"Browser configuration saved for {platform_name}")
                    self.save_config_button.setEnabled(True)
                else:
                    logger.error(f"Failed to save browser configuration for {platform_name}")
            else:
                # Juste synchroniser en mémoire
                self._sync_profile_to_config_provider(platform_name, profile)
                logger.warning("Database not available, saving to memory only")

            self.browser_used.emit(platform_name, browser_type)

        except Exception as e:
            logger.error(f"Error saving browser config: {str(e)}")

    def _save_configuration(self):
        platform_index = self.browser_platform_combo.currentIndex()
        if platform_index <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                "No platform selected",
                "Please select a platform first."
            )
            return

        platform_name = self.browser_platform_combo.currentText()
        
        QtWidgets.QMessageBox.information(
            self,
            "Configuration Saved",
            f"Browser configuration for {platform_name} has been saved successfully!\n\n"
            f"You can now use this platform for AI interactions."
        )