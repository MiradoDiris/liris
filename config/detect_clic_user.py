#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
config/detect_clic_user.py
"""

import time
import threading
from pynput import mouse
from utils.logger import logger


class ClickDetector:
    def __init__(self):
        self.is_listening = False
        self.detected_position = None
        self.listener = None
        self.detection_complete = threading.Event()

    def start_detection(self, timeout=30):
        if self.is_listening:
            return None

        self.is_listening = True
        self.detected_position = None
        self.detection_complete.clear()

        self.listener = mouse.Listener(on_click=self._on_click)
        self.listener.start()

        logger.info("Click detection started. Click on the target window...")

        if self.detection_complete.wait(timeout=timeout):
            self.stop_detection()
            return self.detected_position
        else:
            self.stop_detection()
            logger.warning("Click detection timeout")
            return None

    def stop_detection(self):
        if self.listener:
            self.listener.stop()
            self.listener = None
        
        self.is_listening = False

    def _on_click(self, x, y, button, pressed):
        if pressed and button == mouse.Button.left:
            self.detected_position = {'x': int(x), 'y': int(y)}
            logger.info(f"Click detected at position: ({x}, {y})")
            self.detection_complete.set()
            return False


def detect_window_click(timeout=30):
    detector = ClickDetector()
    return detector.start_detection(timeout)


def save_window_position(platform_name, position, database=None):
    try:
        if database and hasattr(database, 'update_platform_window_position'):
            database.update_platform_window_position(platform_name, position)
            logger.info(f"Window position saved for {platform_name}: {position}")
            return True
        else:
            logger.warning("Database not available for saving window position")
            return False
    except Exception as e:
        logger.error(f"Error saving window position: {str(e)}")
        return False


def get_window_position(platform_name, database=None):
    try:
        if database and hasattr(database, 'get_platform_window_position'):
            position = database.get_platform_window_position(platform_name)
            if position:
                logger.info(f"Window position loaded for {platform_name}: {position}")
                return position
        
        logger.info(f"No window position found for {platform_name}")
        return None
    except Exception as e:
        logger.error(f"Error getting window position: {str(e)}")
        return None