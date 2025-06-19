#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ui/widgets/tabs/prompt_field_widget.py
"""

import os
import json
import time
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle
from config.detect_clic_user import detect_window_click


class PromptFieldWidget(QtWidgets.QWidget):
    prompt_field_configured = pyqtSignal(str, dict)
    prompt_field_detected = pyqtSignal(str, dict)

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
            logger.error(f"Error initializing PromptFieldWidget: {str(e)}")

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        explanation = QtWidgets.QLabel(
            "Configure the prompt field for AI platforms.\n"
            "First ensure your browser window is configured, then click to select the prompt input field."
        )
        explanation.setStyleSheet(PlatformConfigStyle.get_explanation_style())
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(explanation)

        columns_layout = QtWidgets.QHBoxLayout()
        columns_layout.setSpacing(20)

        # Left column
        left_column = QtWidgets.QVBoxLayout()
        left_column.setSpacing(10)

        # Platform selection
        platform_group = QtWidgets.QGroupBox("Platform")
        platform_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        platform_group.setMaximumWidth(300)
        platform_layout = QtWidgets.QVBoxLayout(platform_group)

        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.platform_combo.currentIndexChanged.connect(self._on_platform_selected)
        platform_layout.addWidget(self.platform_combo)

        left_column.addWidget(platform_group)

        # Prerequisites check
        prereq_group = QtWidgets.QGroupBox("Prerequisites")
        prereq_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        prereq_group.setMaximumWidth(300)
        prereq_layout = QtWidgets.QVBoxLayout(prereq_group)

        self.prerequisite_status = QtWidgets.QLabel("Please select a platform")
        self.prerequisite_status.setAlignment(Qt.AlignCenter)
        self.prerequisite_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.prerequisite_status.setWordWrap(True)
        prereq_layout.addWidget(self.prerequisite_status)

        left_column.addWidget(prereq_group)

        # Actions
        actions_group = QtWidgets.QGroupBox("Actions")
        actions_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        actions_group.setMaximumWidth(300)
        actions_layout = QtWidgets.QVBoxLayout(actions_group)

        self.capture_field_button = QtWidgets.QPushButton("📝 Click to Select Prompt Field")
        self.capture_field_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.capture_field_button.clicked.connect(self._capture_prompt_field)
        self.capture_field_button.setEnabled(False)
        actions_layout.addWidget(self.capture_field_button)

        self.field_status = QtWidgets.QLabel("No field position configured")
        self.field_status.setAlignment(Qt.AlignCenter)
        self.field_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.field_status.setWordWrap(True)
        actions_layout.addWidget(self.field_status)

        self.test_config_button = QtWidgets.QPushButton("🧪 Test Prompt Field")
        self.test_config_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.test_config_button.clicked.connect(self._test_configuration)
        self.test_config_button.setEnabled(False)
        actions_layout.addWidget(self.test_config_button)

        self.test_status = QtWidgets.QLabel("No test performed")
        self.test_status.setAlignment(Qt.AlignCenter)
        self.test_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.test_status.setWordWrap(True)
        actions_layout.addWidget(self.test_status)

        left_column.addWidget(actions_group)

        # Save section
        save_group = QtWidgets.QGroupBox("Save")
        save_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        save_group.setMaximumWidth(300)
        save_layout = QtWidgets.QVBoxLayout(save_group)

        self.save_config_button = QtWidgets.QPushButton("💾 Save Configuration")
        self.save_config_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_config_button.clicked.connect(self._save_configuration)
        self.save_config_button.setEnabled(False)
        save_layout.addWidget(self.save_config_button)

        left_column.addWidget(save_group)
        left_column.addStretch()

        # Right column
        right_column = QtWidgets.QVBoxLayout()

        # Input configuration
        config_group = QtWidgets.QGroupBox("Input Configuration")
        config_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        config_form = QtWidgets.QFormLayout(config_group)

        self.submit_method_combo = QtWidgets.QComboBox()
        self.submit_method_combo.addItems([
            "Enter",
            "Ctrl + Enter", 
            "Shift + Enter"
        ])
        self.submit_method_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        config_form.addRow("Submit Method:", self.submit_method_combo)

        self.clear_field_check = QtWidgets.QCheckBox("Clear field before typing")
        self.clear_field_check.setChecked(True)
        config_form.addRow("", self.clear_field_check)

        right_column.addWidget(config_group)

        # Field information
        info_group = QtWidgets.QGroupBox("Field Information")
        info_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        info_layout = QtWidgets.QVBoxLayout(info_group)

        self.field_info = QtWidgets.QLabel("No field captured yet")
        self.field_info.setWordWrap(True)
        self.field_info.setStyleSheet("color: #555; padding: 15px; background-color: #f8f9fa; border-radius: 8px; font-family: 'Courier New';")
        info_layout.addWidget(self.field_info)

        right_column.addWidget(info_group)

        # How it works
        help_group = QtWidgets.QGroupBox("How It Works")
        help_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        help_layout = QtWidgets.QVBoxLayout(help_group)

        help_text = QtWidgets.QLabel(
            "🎯 <b>Workflow:</b>\n\n"
            "1. Select your platform (browser window must be configured first)\n"
            "2. Navigate to your AI platform in the browser\n"
            "3. Click 'Click to Select Prompt Field' and then click on the text input\n"
            "4. Test the configuration to verify it works\n"
            "5. Save the configuration\n\n"
            "💡 <b>During tests:</b> The system will activate your browser window and click on the prompt field."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #555; padding: 15px; background-color: #f8f9fa; border-radius: 8px; line-height: 1.4;")
        help_layout.addWidget(help_text)

        right_column.addWidget(help_group)
        right_column.addStretch()

        # Assemble columns
        columns_layout.addLayout(left_column, 0)
        columns_layout.addLayout(right_column, 1)

        main_layout.addLayout(columns_layout)

    def set_profiles(self, profiles):
        self.profiles = profiles
        self._update_platforms_combo()

    def select_platform(self, platform_name):
        index = self.platform_combo.findText(platform_name)
        if index >= 0:
            self.platform_combo.setCurrentIndex(index)

    def refresh(self):
        self._update_platforms_combo()

    def _update_platforms_combo(self):
        current_text = self.platform_combo.currentText()

        self.platform_combo.clear()
        self.platform_combo.addItem("-- Select a platform --")

        for name in sorted(self.profiles.keys()):
            self.platform_combo.addItem(name)

        if current_text:
            index = self.platform_combo.findText(current_text)
            if index >= 0:
                self.platform_combo.setCurrentIndex(index)

    def _on_platform_selected(self, index):
        if index <= 0:
            self._reset_ui()
            return

        platform_name = self.platform_combo.currentText()
        profile = self.profiles.get(platform_name, {})

        self._check_prerequisites(platform_name, profile)
        self._load_existing_config(platform_name, profile)

    def _check_prerequisites(self, platform_name, profile):
        browser_config = profile.get('browser', {})
        window_position = profile.get('window_position')
        
        if not browser_config or not browser_config.get('url'):
            self.prerequisite_status.setText("❌ Browser configuration missing. Configure in Browser tab first.")
            self.prerequisite_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
            self.capture_field_button.setEnabled(False)
            return False
            
        if not window_position:
            self.prerequisite_status.setText("❌ Window position missing. Configure in Browser tab first.")
            self.prerequisite_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
            self.capture_field_button.setEnabled(False)
            return False

        self.prerequisite_status.setText("✅ Prerequisites OK. Browser window and URL configured.")
        self.prerequisite_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
        self.capture_field_button.setEnabled(True)

        if platform_name.lower() == 'gemini':
            self.submit_method_combo.setCurrentIndex(1)
        
        return True

    def _load_existing_config(self, platform_name, profile):
        interface_positions = profile.get('interface_positions', {})
        prompt_field = interface_positions.get('prompt_field')
        
        if prompt_field:
            self.field_status.setText(f"Field position: ({prompt_field['center_x']}, {prompt_field['center_y']})")
            self.field_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
            self.test_config_button.setEnabled(True)
            
            self.field_info.setText(
                f"📍 Prompt Field Configuration:\n\n"
                f"Position: ({prompt_field['center_x']}, {prompt_field['center_y']})\n"
                f"Area: {prompt_field.get('width', 100)}x{prompt_field.get('height', 30)}\n"
                f"Capture method: {prompt_field.get('capture_method', 'unknown')}\n"
                f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(prompt_field.get('timestamp', 0)))}"
            )
            
            interface_config = profile.get('interface', {}).get('prompt_field', {})
            if interface_config:
                submission = interface_config.get('submission', {})
                submit_method = submission.get('method', 'enter')
                
                method_map = {'enter': 0, 'ctrl_enter': 1, 'shift_enter': 2}
                method_index = method_map.get(submit_method, 0)
                self.submit_method_combo.setCurrentIndex(method_index)
                
                self.clear_field_check.setChecked(submission.get('auto_clear', True))
                
                self.test_status.setText("Configuration loaded")
                self.test_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
                self.save_config_button.setEnabled(True)
        else:
            self.field_status.setText("No field position configured")
            self.field_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
            self.test_config_button.setEnabled(False)
            self.field_info.setText("No field captured yet")

    def _reset_ui(self):
        self.prerequisite_status.setText("Please select a platform")
        self.prerequisite_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.field_status.setText("No field position configured")
        self.field_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.test_status.setText("No test performed")
        self.test_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        self.capture_field_button.setEnabled(False)
        self.test_config_button.setEnabled(False)
        self.save_config_button.setEnabled(False)
        self.field_info.setText("No field captured yet")

    def _capture_prompt_field(self):
        platform_index = self.platform_combo.currentIndex()
        if platform_index <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                "No platform selected",
                "Please select a platform first."
            )
            return

        platform_name = self.platform_combo.currentText()
        profile = self.profiles.get(platform_name, {})
        
        if not self._check_prerequisites(platform_name, profile):
            return

        QtWidgets.QMessageBox.information(
            self,
            "Prompt Field Capture",
            f"Setup for {platform_name}:\n\n"
            f"1. The system will click on your browser window to activate it\n"
            f"2. Then click exactly on the center of the prompt input field\n\n"
            f"You have 30 seconds to click on the field after window activation."
        )

        self.click_detection_running = True
        self.capture_field_button.setText("⏳ Activating browser window...")
        self.capture_field_button.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        try:
            # Use the stored window position to click and activate the browser window
            window_position = profile.get('window_position')
            if window_position and 'x' in window_position and 'y' in window_position:
                import pyautogui
                pyautogui.click(window_position['x'], window_position['y'])
                time.sleep(0.5)
                
                # Open the platform URL if configured
                browser_config = profile.get('browser', {})
                browser_url = browser_config.get('url', '')
                if browser_url:
                    browser_type = browser_config.get('type', 'Chrome')
                    self.conductor.browser_manager.open_url(browser_url, browser_type, new_window=False)
                    time.sleep(1)

            # Now start the click detection for the prompt field
            self.capture_field_button.setText("⏳ Click on prompt field...")
            QtWidgets.QApplication.processEvents()

            position = detect_window_click(timeout=30)
            
            if position:
                field_position = {
                    'x': position['x'] - 50,
                    'y': position['y'] - 15,
                    'width': 100,
                    'height': 30,
                    'center_x': position['x'],
                    'center_y': position['y'],
                    'capture_method': 'user_click_detection',
                    'timestamp': time.time()
                }
                
                if 'interface_positions' not in profile:
                    profile['interface_positions'] = {}
                
                profile['interface_positions']['prompt_field'] = field_position
                
                if self.database:
                    save_success = self.database.save_platform(platform_name, profile)
                    if save_success:
                        self.profiles[platform_name] = profile
                        
                        self.field_status.setText(f"Field position: ({position['x']}, {position['y']})")
                        self.field_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
                        self.test_config_button.setEnabled(True)
                        
                        self.field_info.setText(
                            f"📍 Prompt Field Configuration:\n\n"
                            f"Position: ({position['x']}, {position['y']})\n"
                            f"Area: 100x30\n"
                            f"Capture method: user_click_detection\n"
                            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        
                        QtWidgets.QMessageBox.information(
                            self,
                            "Field Captured",
                            f"Prompt field position saved: ({position['x']}, {position['y']})\n\n"
                            f"You can now test the configuration."
                        )
                    else:
                        QtWidgets.QMessageBox.critical(
                            self,
                            "Save Error",
                            "Failed to save field position to database."
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
            logger.error(f"Error during field capture: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Capture Error",
                f"An error occurred during field capture:\n{str(e)}"
            )

        finally:
            self.click_detection_running = False
            self.capture_field_button.setText("📝 Click to Select Prompt Field")
            self.capture_field_button.setEnabled(True)

    def _test_configuration(self):
        platform_index = self.platform_combo.currentIndex()
        if platform_index <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                "No platform selected",
                "Please select a platform first."
            )
            return

        platform_name = self.platform_combo.currentText()
        profile = self.profiles.get(platform_name, {})
        
        prompt_field = profile.get('interface_positions', {}).get('prompt_field')
        if not prompt_field:
            QtWidgets.QMessageBox.warning(
                self,
                "No field configured",
                "Please capture the prompt field position first."
            )
            return

        # Important warning before test
        reply = QtWidgets.QMessageBox.information(
            self,
            "Test Starting",
            f"🚨 <b>IMPORTANT:</b>\n\n"
            f"The test will now automatically:\n"
            f"• Click on your browser window to activate it\n"
            f"• Click on the prompt field\n"
            f"• Type a test message\n"
            f"• Submit the message\n\n"
            f"⚠️ <b>DO NOT TOUCH YOUR MOUSE OR KEYBOARD</b> during the test!\n\n"
            f"The test will take about 3-5 seconds.\n"
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
                f"Testing prompt field for {platform_name}...\n\nDO NOT TOUCH MOUSE OR KEYBOARD!",
                "Cancel",
                0, 100,
                self
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setValue(10)

            progress.setLabelText("Activating browser window...\nDO NOT TOUCH MOUSE!")
            progress.setValue(30)

            browser_config = profile.get('browser', {})
            browser_type = browser_config.get('type', 'Chrome')
            browser_url = browser_config.get('url', '')

            activate_result = self.conductor.select_existing_window(
                browser_type=browser_type,
                platform_name=platform_name,
                url=browser_url
            )

            if not activate_result.get('success'):
                progress.cancel()
                self.test_status.setText("Browser activation failed!")
                self.test_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
                QtWidgets.QMessageBox.critical(
                    self,
                    "Test Failed",
                    f"Failed to activate browser window:\n{activate_result.get('message', 'Unknown error')}"
                )
                return

            progress.setValue(60)
            progress.setLabelText("Clicking on prompt field...\nDO NOT TOUCH MOUSE!")

            time.sleep(1)

            import pyautogui
            
            field_x = prompt_field['center_x']
            field_y = prompt_field['center_y']
            
            pyautogui.click(field_x, field_y)
            time.sleep(0.5)

            if self.clear_field_check.isChecked():
                pyautogui.hotkey('ctrl', 'a')
                pyautogui.press('delete')
                time.sleep(0.2)

            test_text = f"Test prompt field - {time.strftime('%H:%M:%S')}"
            pyautogui.typewrite(test_text)
            time.sleep(0.5)

            submit_method_index = self.submit_method_combo.currentIndex()
            if submit_method_index == 0:
                pyautogui.press('enter')
            elif submit_method_index == 1:
                pyautogui.hotkey('ctrl', 'enter')
            elif submit_method_index == 2:
                pyautogui.hotkey('shift', 'enter')

            progress.setValue(100)

            self.test_status.setText("Test successful!")
            self.test_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

            QtWidgets.QMessageBox.information(
                self,
                "Test Successful",
                f"Prompt field test successful for {platform_name}!\n\n"
                f"✅ Browser window activated\n"
                f"✅ Prompt field clicked at ({field_x}, {field_y})\n"
                f"✅ Test text entered and submitted\n\n"
                f"The prompt field configuration is working correctly.\n"
                f"You can now safely use your mouse and keyboard again."
            )

            self.save_config_button.setEnabled(True)

        except Exception as e:
            logger.error(f"Error during test: {str(e)}")
            self.test_status.setText("Test failed!")
            self.test_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())

            QtWidgets.QMessageBox.critical(
                self,
                "Test Error",
                f"An error occurred during testing:\n{str(e)}\n\n"
                f"You can now safely use your mouse and keyboard again."
            )

    def _save_configuration(self):
        platform_index = self.platform_combo.currentIndex()
        if platform_index <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                "No platform selected",
                "Please select a platform first."
            )
            return

        platform_name = self.platform_combo.currentText()
        profile = self.profiles.get(platform_name, {})
        
        prompt_field = profile.get('interface_positions', {}).get('prompt_field')
        if not prompt_field:
            QtWidgets.QMessageBox.warning(
                self,
                "No field configured",
                "Please capture and test the prompt field first."
            )
            return

        try:
            if 'interface' not in profile:
                profile['interface'] = {}

            method_map = {0: 'enter', 1: 'ctrl_enter', 2: 'shift_enter'}
            submit_method = method_map.get(self.submit_method_combo.currentIndex(), 'enter')

            prompt_field_config = {
                "type": "captured_field",
                "detection": {
                    "method": "user_click_detection",
                    "capture_timestamp": prompt_field.get('timestamp', time.time()),
                    "validation_passed": True
                },
                "submission": {
                    "method": submit_method,
                    "auto_clear": self.clear_field_check.isChecked()
                }
            }

            profile['interface']['prompt_field'] = prompt_field_config

            if self.database:
                save_success = self.database.save_platform(platform_name, profile)
                if save_success:
                    self.profiles[platform_name] = profile
                    
                    self.prompt_field_configured.emit(platform_name, prompt_field_config)
                    self.prompt_field_detected.emit(platform_name, prompt_field)
                    
                    QtWidgets.QMessageBox.information(
                        self,
                        "Configuration Saved",
                        f"Prompt field configuration for {platform_name} saved successfully!\n\n"
                        f"You can now use this platform for AI interactions."
                    )
                else:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Save Error",
                        "Failed to save configuration to database."
                    )
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Database Error",
                    "Database not available for saving configuration."
                )

        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Save Error",
                f"An error occurred while saving:\n{str(e)}"
            )