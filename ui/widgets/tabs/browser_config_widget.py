#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ui/widgets/tabs/browser_config_widget.py
"""

import os
import json
import traceback
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle


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
        self.saved_browsers = {}
        self.profiles = {}
        self.database = getattr(conductor, 'database', None)

        try:
            self._init_ui()
            self._load_saved_browsers()
        except Exception as e:
            logger.error(f"Error initializing BrowserConfigWidget: {str(e)}")

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        explanation = QtWidgets.QLabel(
            "Configure browser settings for AI platforms.\n"
            "You can now use multiple platforms with the same browser by specifying window numbers.\n"
            "Start by selecting your platform, then configure the browser and test the connection."
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

        self.browser_platform_combo = QtWidgets.QComboBox()
        self.browser_platform_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.browser_platform_combo.currentIndexChanged.connect(self._on_platform_selected)
        platform_layout.addWidget(self.browser_platform_combo)

        left_column.addWidget(platform_group)

        # Actions
        actions_group = QtWidgets.QGroupBox("Actions")
        actions_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        actions_group.setMaximumWidth(300)
        actions_layout = QtWidgets.QVBoxLayout(actions_group)

        self.test_browser_button = QtWidgets.QPushButton("◉ Test Browser")
        self.test_browser_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.test_browser_button.clicked.connect(self._test_browser)
        actions_layout.addWidget(self.test_browser_button)

        self.detection_status = QtWidgets.QLabel("No test performed")
        self.detection_status.setAlignment(Qt.AlignCenter)
        self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        actions_layout.addWidget(self.detection_status)

        self.remember_positions_check = QtWidgets.QCheckBox("Remember detected positions")
        self.remember_positions_check.setChecked(True)
        actions_layout.addWidget(self.remember_positions_check)

        self.force_detect_check = QtWidgets.QCheckBox("Force detection each time")
        actions_layout.addWidget(self.force_detect_check)

        left_column.addWidget(actions_group)

        # Saved browsers
        saved_browsers_group = QtWidgets.QGroupBox("Saved Browsers")
        saved_browsers_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        saved_browsers_group.setMaximumWidth(300)
        saved_browsers_layout = QtWidgets.QVBoxLayout(saved_browsers_group)

        self.saved_browsers_list = QtWidgets.QListWidget()
        self.saved_browsers_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.saved_browsers_list.currentItemChanged.connect(self._on_saved_browser_selected)
        self.saved_browsers_list.setStyleSheet(PlatformConfigStyle.get_small_list_style())
        saved_browsers_layout.addWidget(self.saved_browsers_list)

        saved_browsers_buttons = QtWidgets.QHBoxLayout()

        self.edit_browser_button = QtWidgets.QPushButton("Edit")
        self.edit_browser_button.clicked.connect(self._edit_browser)
        self.edit_browser_button.setStyleSheet(PlatformConfigStyle.get_button_style())

        self.delete_browser_button = QtWidgets.QPushButton("Delete")
        self.delete_browser_button.clicked.connect(self._delete_browser)
        self.delete_browser_button.setStyleSheet(PlatformConfigStyle.get_button_style())

        saved_browsers_buttons.addWidget(self.edit_browser_button)
        saved_browsers_buttons.addWidget(self.delete_browser_button)

        saved_browsers_layout.addLayout(saved_browsers_buttons)

        left_column.addWidget(saved_browsers_group)

        # Save section
        save_group = QtWidgets.QGroupBox("Save")
        save_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        save_group.setMaximumWidth(300)
        save_layout = QtWidgets.QVBoxLayout(save_group)

        self.save_browser_button = QtWidgets.QPushButton("⬇ Save Configuration")
        self.save_browser_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_browser_button.clicked.connect(self._save_browser_config)
        save_layout.addWidget(self.save_browser_button)

        left_column.addWidget(save_group)
        left_column.addStretch()

        # Right column
        right_column = QtWidgets.QVBoxLayout()

        # Browser configuration
        browser_form_group = QtWidgets.QGroupBox("Browser Configuration")
        browser_form_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        browser_form = QtWidgets.QFormLayout(browser_form_group)

        self.browser_name_edit = QtWidgets.QLineEdit()
        self.browser_name_edit.setPlaceholderText("Configuration name (e.g., Firefox Personal)")
        self.browser_name_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        browser_form.addRow("Name:", self.browser_name_edit)

        self.browser_type_combo = QtWidgets.QComboBox()
        self.browser_type_combo.addItems(["Chrome", "Firefox", "Edge", "Safari", "Other"])
        self.browser_type_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        browser_form.addRow("Browser Type:", self.browser_type_combo)

        self.browser_path_edit = QtWidgets.QLineEdit()
        self.browser_path_edit.setPlaceholderText("Path to browser executable (empty = default)")
        self.browser_path_edit.setStyleSheet(PlatformConfigStyle.get_input_style())

        path_layout = QtWidgets.QHBoxLayout()
        self.browser_path_browse = QtWidgets.QPushButton("...")
        self.browser_path_browse.setMaximumWidth(30)
        self.browser_path_browse.clicked.connect(self._browse_browser_path)
        self.browser_path_browse.setStyleSheet(PlatformConfigStyle.get_button_style())
        path_layout.addWidget(self.browser_path_edit)
        path_layout.addWidget(self.browser_path_browse)
        browser_form.addRow("Path:", path_layout)

        self.browser_url_edit = QtWidgets.QLineEdit()
        self.browser_url_edit.setPlaceholderText("Platform URL (e.g., https://chat.openai.com)")
        self.browser_url_edit.setStyleSheet(PlatformConfigStyle.get_input_style())
        browser_form.addRow("URL:", self.browser_url_edit)

        self.window_number_spin = QtWidgets.QSpinBox()
        self.window_number_spin.setRange(1, 10)
        self.window_number_spin.setValue(1)
        self.window_number_spin.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.window_number_spin.setToolTip("Window number in taskbar (1 = first)")
        browser_form.addRow("Window Number:", self.window_number_spin)

        # Window selection mode
        self.window_mode_combo = QtWidgets.QComboBox()
        self.window_mode_combo.addItems(["Select existing window", "Open new window"])
        self.window_mode_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.window_mode_combo.setToolTip("Choose to select existing window or open new one")
        browser_form.addRow("Window Mode:", self.window_mode_combo)

        right_column.addWidget(browser_form_group)

        # Browser options
        options_group = QtWidgets.QGroupBox("Browser Options")
        options_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        options_layout = QtWidgets.QVBoxLayout(options_group)

        self.maximize_window_check = QtWidgets.QCheckBox("Maximize window (recommended)")
        self.maximize_window_check.setChecked(True)
        self.maximize_window_check.setToolTip("Maximize browser window for better detection")
        options_layout.addWidget(self.maximize_window_check)

        self.incognito_mode_check = QtWidgets.QCheckBox("Private/Incognito mode")
        self.incognito_mode_check.setChecked(False)
        self.incognito_mode_check.setToolTip("Launch browser in private browsing mode")
        options_layout.addWidget(self.incognito_mode_check)

        self.disable_extensions_check = QtWidgets.QCheckBox("Disable extensions")
        self.disable_extensions_check.setChecked(False)
        self.disable_extensions_check.setToolTip("Launch browser without extensions to avoid interference")
        options_layout.addWidget(self.disable_extensions_check)

        right_column.addWidget(options_group)

        # Detection info
        info_group = QtWidgets.QGroupBox("Detection Information")
        info_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        info_layout = QtWidgets.QVBoxLayout(info_group)

        info_text = QtWidgets.QLabel(
            "Browser test will:\n\n"
            "🔹 Select existing window mode:\n"
            "  - Find already open browser windows\n"
            "  - Select window according to specified number\n"
            "  - Focus and maximize the selected window\n\n"
            "🔹 Open new window mode:\n"
            "  - Open browser to specified URL\n"
            "  - Create new window or tab\n"
            "  - Select window according to specified number\n\n"
            "💡 Use 'Select existing window' for normal workflow.\n"
            "Use 'Open new window' only for initial setup.\n\n"
            "This test does NOT configure interface elements yet.\n"
            "Use the following tabs for that."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: #555; padding: 10px; background-color: #f8f9fa; border-radius: 5px;")
        info_layout.addWidget(info_text)

        right_column.addWidget(info_group)

        columns_layout.addLayout(left_column, 0)
        columns_layout.addLayout(right_column, 1)

        main_layout.addLayout(columns_layout)

        help_note = QtWidgets.QLabel(
            "<b>Workflow:</b> 1▸ Select platform → 2▸ Configure browser and window number → "
            "3▸ Choose window mode (existing/new) → 4▸ Test connection → 5▸ Save configuration"
        )
        help_note.setWordWrap(True)
        help_note.setStyleSheet("color: #074E68; padding: 10px; font-style: italic;")
        help_note.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(help_note)

    def set_profiles(self, profiles):
        self.profiles = profiles
        self._update_platforms_combo()

    def select_platform(self, platform_name):
        index = self.browser_platform_combo.findText(platform_name)
        if index >= 0:
            self.browser_platform_combo.setCurrentIndex(index)

    def should_force_detect(self):
        return self.force_detect_check.isChecked()

    def should_remember_positions(self):
        return self.remember_positions_check.isChecked()

    def refresh(self):
        self._load_saved_browsers()
        self._update_platforms_combo()

    def _load_saved_browsers(self):
        try:
            browsers_dir = os.path.join(getattr(self.config_provider, 'profiles_dir', 'config/profiles'), 'browsers')
            if not os.path.exists(browsers_dir):
                os.makedirs(browsers_dir, exist_ok=True)
                return

            self.saved_browsers = {}

            for filename in os.listdir(browsers_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(browsers_dir, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            browser_config = json.load(f)
                            name = browser_config.get('name', filename.replace('.json', ''))
                            self.saved_browsers[name] = browser_config
                    except Exception as e:
                        logger.error(f"Error loading browser {filename}: {str(e)}")

            self._update_saved_browsers_list()

        except Exception as e:
            logger.error(f"Error loading browsers: {str(e)}")

    def _update_saved_browsers_list(self):
        self.saved_browsers_list.clear()
        for name in sorted(self.saved_browsers.keys()):
            self.saved_browsers_list.addItem(name)

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

    def _browse_browser_path(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Browser",
            "",
            "Executables (*.exe);;All Files (*.*)"
        )

        if file_path:
            self.browser_path_edit.setText(file_path)

    def _on_platform_selected(self, index):
        if index <= 0:
            return

        platform_name = self.browser_platform_combo.currentText()

        profile = self.profiles.get(platform_name, {})
        browser_info = profile.get('browser', {})

        self.browser_name_edit.setText(f"Browser for {platform_name}")

        browser_type = browser_info.get('type', 'Chrome')
        index = self.browser_type_combo.findText(browser_type)
        if index >= 0:
            self.browser_type_combo.setCurrentIndex(index)

        self.browser_path_edit.setText(browser_info.get('path', ''))
        self.browser_url_edit.setText(browser_info.get('url', ''))
        self.maximize_window_check.setChecked(True)

        window_order = browser_info.get('window_order', 1)
        self.window_number_spin.setValue(window_order)

        # Set default window mode to existing window selection
        self.window_mode_combo.setCurrentIndex(0)  # "Select existing window"

        if 'interface_positions' in profile:
            self.detection_status.setText("Interface positions remembered")
            self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())
        else:
            self.detection_status.setText("No test performed")
            self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())

    def _on_saved_browser_selected(self, current, previous):
        if not current:
            return

        browser_name = current.text()
        browser_config = self.saved_browsers.get(browser_name, {})

        self.browser_name_edit.setText(browser_name)

        browser_type = browser_config.get('type', 'Chrome')
        index = self.browser_type_combo.findText(browser_type)
        if index >= 0:
            self.browser_type_combo.setCurrentIndex(index)

        self.browser_path_edit.setText(browser_config.get('path', ''))
        self.browser_url_edit.setText(browser_config.get('url', ''))
        self.maximize_window_check.setChecked(True)

        window_order = browser_config.get('window_order', 1)
        self.window_number_spin.setValue(window_order)

        # Set default window mode
        self.window_mode_combo.setCurrentIndex(0)  # "Select existing window"

        # Set default window mode
        self.window_mode_combo.setCurrentIndex(0)  # "Select existing window"

    def _edit_browser(self):
        if not self.saved_browsers_list.currentItem():
            QtWidgets.QMessageBox.warning(
                self,
                "No browser selected",
                "Please select a browser first."
            )
            return

        browser_name = self.saved_browsers_list.currentItem().text()
        browser_config = self.saved_browsers.get(browser_name, {})

        self.browser_name_edit.setText(browser_name)

        browser_type = browser_config.get('type', 'Chrome')
        index = self.browser_type_combo.findText(browser_type)
        if index >= 0:
            self.browser_type_combo.setCurrentIndex(index)

        self.browser_path_edit.setText(browser_config.get('path', ''))
        self.browser_url_edit.setText(browser_config.get('url', ''))
        self.maximize_window_check.setChecked(True)

        window_order = browser_config.get('window_order', 1)
        self.window_number_spin.setValue(window_order)

        QtWidgets.QMessageBox.information(
            self,
            "Browser loaded",
            f"Browser configuration '{browser_name}' loaded for editing. Use 'Test Browser' button to verify and save changes."
        )

    def _test_browser(self):
        """Test browser using appropriate method based on window mode"""
        platform_index = self.browser_platform_combo.currentIndex()
        if platform_index <= 0:
            QtWidgets.QMessageBox.warning(
                self,
                "No platform selected",
                "Please select a platform first."
            )
            return

        name = self.browser_name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(
                self,
                "Name missing",
                "Please enter a name for this browser configuration."
            )
            return

        platform_name = self.browser_platform_combo.currentText()

        self.detection_status.setText("Testing...")
        self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_normal_style())
        QtWidgets.QApplication.processEvents()

        try:
            browser_type = self.browser_type_combo.currentText()
            browser_path = self.browser_path_edit.text()
            browser_url = self.browser_url_edit.text().strip()
            window_number = self.window_number_spin.value()
            window_mode = self.window_mode_combo.currentText()

            # Check URL - recommended for both modes but only required for new window
            if not browser_url:
                if "new window" in window_mode.lower():
                    QtWidgets.QMessageBox.warning(
                        self,
                        "URL missing",
                        "Please specify the website URL for opening new window."
                    )
                    self.detection_status.setText("Test cancelled: URL missing")
                    self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
                    return
                else:
                    # URL optional for existing window mode, but recommend it
                    reply = QtWidgets.QMessageBox.question(
                        self,
                        "No URL specified",
                        "No URL specified. The existing window will be selected but no new tab will be opened.\n\n"
                        "Do you want to continue without opening the platform URL?",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.No
                    )
                    if reply != QtWidgets.QMessageBox.Yes:
                        self.detection_status.setText("Test cancelled by user")
                        self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())
                        return

            progress = QtWidgets.QProgressDialog(
                f"Testing browser for {platform_name} (window #{window_number})...",
                "Cancel",
                0, 100,
                self
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setValue(10)

            # Choose method based on window mode
            if "existing" in window_mode.lower():
                # Select existing window
                progress.setLabelText("Selecting existing window...")
                progress.setValue(50)

                result = self.conductor.select_existing_window(
                    browser_type=browser_type,
                    window_order=window_number,
                    platform_name=platform_name,
                    url=browser_url  # Pass URL to open in selected window
                )
            else:
                # Open new window
                progress.setLabelText("Opening new browser window...")
                progress.setValue(30)

                result = self.conductor.open_browser_only(
                    browser_type=browser_type,
                    url=browser_url,
                    window_order=window_number,
                    new_window=True,
                    platform_name=platform_name
                )

            progress.setValue(80)

            if result.get('success'):
                progress.setValue(100)

                self.detection_status.setText("Test successful!")
                self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_success_style())

                duration = result.get('duration', 0)
                selected_window = result.get('selected_window', {})
                window_title = selected_window.get('title', 'Unknown')
                method = result.get('method', 'unknown')
                url_opened = result.get('url_opened', False)

                success_message = (
                    f"Browser {browser_type} test successful for {platform_name}.\n"
                    f"Window selected: #{window_number} - {window_title}\n"
                    f"Test completed in {duration:.1f}s\n"
                    f"Method: {method}\n"
                    f"Config source: {result.get('config_source', 'default')}\n"
                )
                
                if "existing" in window_mode.lower():
                    if url_opened:
                        success_message += f"Platform URL opened in new tab: {browser_url}\n"
                    elif browser_url:
                        success_message += "Note: URL was specified but may not have opened.\n"
                    else:
                        success_message += "No URL was opened (window selection only).\n"
                
                success_message += "\nBrowser is configured and ready to use.\nYou can now proceed to the next tabs to configure interface elements."

                QtWidgets.QMessageBox.information(
                    self,
                    "Test Successful",
                    success_message
                )

                self._save_successful_config(platform_name, browser_type, browser_path, browser_url, window_number)

            else:
                progress.cancel()
                error_msg = result.get('message', 'Unknown error')
                available_windows = result.get('available_windows', 0)
                
                self.detection_status.setText(f"Failed: {error_msg}")
                self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())

                if "existing" in window_mode.lower():
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Window Selection Failed",
                        f"Window selection failed: {error_msg}\n\n"
                        f"Available {browser_type} windows: {available_windows}\n"
                        f"Requested window: #{window_number}\n\n"
                        f"Please:\n"
                        f"- Open {browser_type} browser first\n"
                        f"- Choose a valid window number (1-{available_windows})\n"
                        f"- Or switch to 'Open new window' mode"
                    )
                else:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Browser Test Failed",
                        f"Browser opening failed: {error_msg}\n\n"
                        f"Please verify:\n"
                        f"- URL is correct\n"
                        f"- Browser is installed\n"
                        f"- No other browser instance is blocking"
                    )

        except Exception as e:
            logger.error(f"Error during test: {str(e)}")
            self.detection_status.setText(f"Error: {str(e)}")
            self.detection_status.setStyleSheet(PlatformConfigStyle.get_status_error_style())

            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"An error occurred during testing: {str(e)}"
            )

    def _save_successful_config(self, platform_name, browser_type, browser_path, browser_url, window_number):
        """Save configuration after successful test"""
        try:
            profile = self.profiles.get(platform_name, {})

            browser_config = {
                "type": browser_type,
                "path": browser_path,
                "url": browser_url,
                "fullscreen": False,
                "window_selection_method": "order",
                "window_order": window_number,
                "window_title_pattern": "",
                "window_position": None,
                "window_id": None,
                "window_size": None,
                "remember_window": False
            }

            if 'browser' not in profile:
                profile['browser'] = {}
            profile['browser'].update(browser_config)

            if self.database:
                save_success = self.database.save_platform(platform_name, profile)
                if save_success:
                    logger.info(f"Configuration saved for {platform_name}")
                else:
                    logger.error(f"Failed to save configuration for {platform_name}")
            else:
                self.profiles[platform_name] = profile
                logger.warning("Database not available, saving to memory only")

            self.browser_used.emit(platform_name, browser_type)

        except Exception as e:
            logger.error(f"Error saving successful test config: {str(e)}")

    def _save_browser_config(self):
        """Save current browser configuration"""
        name = self.browser_name_edit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(
                self,
                "Name missing",
                "Please enter a name for this browser configuration."
            )
            return

        browser_config = {
            "name": name,
            "type": self.browser_type_combo.currentText(),
            "path": self.browser_path_edit.text(),
            "url": self.browser_url_edit.text(),
            "fullscreen": False,
            "window_order": self.window_number_spin.value()
        }

        try:
            self.saved_browsers[name] = browser_config

            browsers_dir = os.path.join(getattr(self.config_provider, 'profiles_dir', 'config/profiles'), 'browsers')
            os.makedirs(browsers_dir, exist_ok=True)

            file_path = os.path.join(browsers_dir, f"{name}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(browser_config, f, indent=2, ensure_ascii=False)

            self._update_saved_browsers_list()
            self.browser_saved.emit(name, browser_config)

            QtWidgets.QMessageBox.information(
                self,
                "Configuration Saved",
                f"Browser configuration '{name}' saved successfully."
            )

        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Save Error",
                f"Cannot save configuration: {str(e)}"
            )

    def _delete_browser(self):
        """Delete selected browser configuration"""
        if not self.saved_browsers_list.currentItem():
            return

        browser_name = self.saved_browsers_list.currentItem().text()

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete configuration '{browser_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            if browser_name in self.saved_browsers:
                del self.saved_browsers[browser_name]

            browsers_dir = os.path.join(getattr(self.config_provider, 'profiles_dir', 'config/profiles'), 'browsers')
            file_path = os.path.join(browsers_dir, f"{browser_name}.json")

            if os.path.exists(file_path):
                os.remove(file_path)

            self._update_saved_browsers_list()
            self.browser_deleted.emit(browser_name)

            QtWidgets.QMessageBox.information(
                self,
                "Configuration Deleted",
                f"Browser configuration '{browser_name}' deleted."
            )

        except Exception as e:
            logger.error(f"Error deleting configuration: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Delete Error",
                f"Cannot delete configuration: {str(e)}"
            )