#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/tabs/prompt_field_widget.py - VERSION CORRIGÉE FINALE

CORRECTIONS APPLIQUÉES :
✅ Overlay NON-BLOQUANT (countdown 6s au lieu de 30s)
✅ Flags PyQt5 optimisés pour éviter le blocage système
✅ Zone instructions 100% protégée contre les clics
✅ Crosshair précis seulement en dehors des instructions
✅ Compatibilité avec architecture conductor.py corrigée
✅ Simplicité > Complexité (même principe que conductor)
"""

import os
import json
import traceback
import time
import threading
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt5.QtGui import QCursor, QPainter, QBrush, QColor, QFont, QPixmap, QPen

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle

try:
    import pyautogui
    import pygetwindow as gw
    HAS_CAPTURE_TOOLS = True
except ImportError:
    HAS_CAPTURE_TOOLS = False
    logger.warning("Outils de capture non disponibles")


class CaptureOverlay(QtWidgets.QWidget):
    """CORRIGÉ: Overlay NON-BLOQUANT avec countdown 6s et zone instructions protégée"""
    click_captured = pyqtSignal(int, int)  # x, y
    capture_cancelled = pyqtSignal()
    
    def __init__(self, element_type="field"):
        super().__init__()
        self.element_type = element_type
        self.mouse_pos = QtCore.QPoint(0, 0)
        self.countdown = 6  # ✅ CORRIGÉ: 6s au lieu de 30s
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_countdown)
        self.instruction_rect = QtCore.QRect()  # Zone des instructions protégée
        
        self.setupUI()
        
    def setupUI(self):
        """CORRIGÉ: Configuration overlay NON-BLOQUANT"""
        # ✅ CORRIGÉ: Flags de fenêtre optimisés pour NE PAS bloquer le système
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | 
            Qt.FramelessWindowHint | 
            Qt.Tool
        )
        
        # ✅ CORRIGÉ: Attributs pour non-blocage
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Optionnel selon OS - peut aider à éviter le blocage
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        self.setGeometry(QtWidgets.QApplication.desktop().screenGeometry())
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        
        # ✅ CORRIGÉ: Zone d'instructions optimisée et compacte
        screen = QtWidgets.QApplication.desktop().screenGeometry()
        center = screen.center()
        # Zone plus petite et mieux positionnée
        self.instruction_rect = QtCore.QRect(center.x() - 300, center.y() - 140, 600, 280)
        
    def showOverlay(self):
        """Affiche l'overlay NON-BLOQUANT et démarre le countdown 6s"""
        self.show()
        self.activateWindow()
        self.raise_()
        self.timer.start(1000)  # 1 seconde
        logger.info("✅ Overlay NON-BLOQUANT activé (countdown 6s)")
        
    def _update_countdown(self):
        """✅ CORRIGÉ: Countdown RAPIDE (6s)"""
        self.countdown -= 1
        self.update()  # Redessiner l'overlay
        
        if self.countdown <= 0:
            self.timer.stop()
            logger.warning("⏰ TIMEOUT overlay après 6 secondes")
            self.capture_cancelled.emit()
            self.close()
    
    def mouseMoveEvent(self, event):
        """Track la position de la souris pour le crosshair"""
        self.mouse_pos = event.pos()
        self.update()  # Redessiner pour actualiser le crosshair
        
    def mousePressEvent(self, event):
        """✅ CORRIGÉ: Capture clic SEULEMENT EN DEHORS de la zone d'instructions"""
        if event.button() == Qt.LeftButton:
            # ✅ CORRIGÉ: Vérifier si le clic est dans la zone d'instructions
            if self.instruction_rect.contains(event.pos()):
                # Clic dans les instructions = ne rien faire, juste ignorer
                logger.debug("Clic dans zone instructions - ignoré")
                return  # ❌ Ne rien faire
            
            # ✅ CORRIGÉ: Clic EN DEHORS des instructions = capturer la position
            global_pos = self.mapToGlobal(event.pos())
            self.timer.stop()
            logger.info(f"✅ CLIC CAPTURÉ: ({global_pos.x()}, {global_pos.y()})")
            self.click_captured.emit(global_pos.x(), global_pos.y())
            self.close()
            
    def keyPressEvent(self, event):
        """Gère les touches clavier (ÉCHAP pour annuler)"""
        if event.key() == Qt.Key_Escape:
            self.timer.stop()
            logger.info("❌ ÉCHAP pressé - fermeture overlay")
            self.capture_cancelled.emit()
            self.close()
    
    def paintEvent(self, event):
        """✅ CORRIGÉ: Dessine l'overlay avec zone cliquable bien définie"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # ✅ CORRIGÉ: Fond très léger pour ne pas bloquer la vue
        full_rect = self.rect()
        painter.fillRect(full_rect, QColor(0, 0, 0, 30))  # Plus transparent
        
        # ✅ CORRIGÉ: Zone d'instructions avec fond opaque pour bien la distinguer
        painter.setBrush(QBrush(QColor(255, 255, 255, 250)))
        painter.setPen(QPen(QColor(0, 120, 215), 3))
        painter.drawRoundedRect(self.instruction_rect, 15, 15)
        
        # Titre principal
        painter.setPen(QColor(0, 120, 215))
        title_font = QFont("Segoe UI", 20, QFont.Bold)
        painter.setFont(title_font)
        
        element_text = "CHAMP DE PROMPT" if self.element_type == "field" else "BOUTON DE SOUMISSION"
        title_rect = QtCore.QRect(self.instruction_rect.x(), self.instruction_rect.y() + 20, self.instruction_rect.width(), 50)
        painter.drawText(title_rect, Qt.AlignCenter, f"🎯 CLIQUEZ SUR LE {element_text}")
        
        # ✅ CORRIGÉ: Instructions détaillées et compactes
        painter.setPen(QColor(60, 60, 60))
        instruction_font = QFont("Segoe UI", 13)
        painter.setFont(instruction_font)
        
        if self.element_type == "field":
            instructions = [
                "• Allez dans votre navigateur",
                "• Cliquez EXACTEMENT dans le champ de saisie du prompt",
                "• Cliquez au centre du champ pour une précision maximale",
                "",
                "⚠️ IMPORTANT : Cliquez EN DEHORS de cette zone d'instructions !"
            ]
        else:
            instructions = [
                "• Allez dans votre navigateur", 
                "• Cliquez EXACTEMENT sur le bouton d'envoi",
                "• Généralement un bouton avec une flèche ou 'Envoyer'",
                "",
                "⚠️ IMPORTANT : Cliquez EN DEHORS de cette zone d'instructions !"
            ]
            
        y_offset = 80
        for instruction in instructions:
            if instruction == "":
                y_offset += 15
                continue
                
            text_rect = QtCore.QRect(self.instruction_rect.x() + 30, self.instruction_rect.y() + y_offset, self.instruction_rect.width() - 60, 25)
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, instruction)
            y_offset += 26
            
        # ✅ CORRIGÉ: Countdown URGENT (6s) bien visible
        painter.setPen(QColor(220, 53, 69))
        countdown_font = QFont("Segoe UI", 16, QFont.Bold)
        painter.setFont(countdown_font)
        countdown_rect = QtCore.QRect(self.instruction_rect.x(), self.instruction_rect.y() + 210, self.instruction_rect.width(), 30)
        painter.drawText(countdown_rect, Qt.AlignCenter, f"⏰ Fermeture automatique: {self.countdown}s")
        
        # Contrôles
        painter.setPen(QColor(108, 117, 125))
        control_font = QFont("Segoe UI", 11)
        painter.setFont(control_font)
        control_rect = QtCore.QRect(self.instruction_rect.x(), self.instruction_rect.y() + 240, self.instruction_rect.width(), 25)
        painter.drawText(control_rect, Qt.AlignCenter, "Appuyez sur ÉCHAP pour annuler")
        
        # ✅ CORRIGÉ: Crosshair SEULEMENT en dehors de la zone d'instructions
        if self.mouse_pos != QtCore.QPoint(0, 0) and not self.instruction_rect.contains(self.mouse_pos):
            painter.setPen(QPen(QColor(255, 0, 0, 180), 2))
            # Ligne horizontale
            painter.drawLine(0, self.mouse_pos.y(), self.width(), self.mouse_pos.y())
            # Ligne verticale  
            painter.drawLine(self.mouse_pos.x(), 0, self.mouse_pos.x(), self.height())
            
            # Coordonnées en temps réel
            painter.setPen(QColor(255, 255, 255))
            coords_font = QFont("Consolas", 10, QFont.Bold)
            painter.setFont(coords_font)
            
            global_mouse = self.mapToGlobal(self.mouse_pos)
            coords_text = f"({global_mouse.x()}, {global_mouse.y()})"
            
            # Fond pour les coordonnées
            metrics = painter.fontMetrics()
            text_width = metrics.width(coords_text)
            coords_bg_rect = QtCore.QRect(self.mouse_pos.x() + 15, self.mouse_pos.y() - 25, text_width + 10, 20)
            painter.fillRect(coords_bg_rect, QColor(0, 0, 0, 180))
            
            coords_rect = QtCore.QRect(self.mouse_pos.x() + 20, self.mouse_pos.y() - 20, text_width, 15)
            painter.drawText(coords_rect, Qt.AlignLeft, coords_text)


class PromptFieldWidget(QtWidgets.QWidget):
    """✅ CORRIGÉ: Widget avec overlay NON-BLOQUANT et workflow simplifié"""

    # Signaux
    prompt_field_configured = pyqtSignal(str, dict)
    prompt_field_detected = pyqtSignal(str, dict)
    submit_button_detected = pyqtSignal(str, dict)

    def __init__(self, config_provider, conductor, parent=None):
        """Initialise le widget CORRIGÉ"""
        super().__init__(parent)

        logger.info("🎯 PromptFieldWidget: Version CORRIGÉE avec overlay NON-BLOQUANT (6s)")

        self.config_provider = config_provider
        self.conductor = conductor
        self.profiles = {}
        self.current_platform = None
        self.current_profile = None
        
        # États du workflow (PRÉSERVÉS)
        self.browser_opened = False
        self.field_captured = False
        self.button_captured = False
        self.validation_done = False
        
        # Système de capture CORRIGÉ
        self.overlay = None
        self.is_capturing = False
        self.captured_positions = {}
        self.current_capture_type = None
        
        if not HAS_CAPTURE_TOOLS:
            logger.warning("Outils de capture non disponibles")

        try:
            self._init_ui()
            logger.info("✅ PromptFieldWidget CORRIGÉ avec overlay NON-BLOQUANT initialisé")
        except Exception as e:
            logger.error(f"Erreur initialisation: {str(e)}")
            print(f"ERREUR CRITIQUE: {str(e)}")
            print(traceback.format_exc())

    def _init_ui(self):
        """✅ CORRIGÉ: Interface avec mentions overlay NON-BLOQUANT"""
        # Layout principal
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # ✅ CORRIGÉ: Explication avec mentions corrections
        explanation = QtWidgets.QLabel(
            "🎯 <b>Workflow CORRIGÉ :</b><br>"
            "1▸ Ouvrir navigateur → 2▸ Overlay NON-BLOQUANT (6s) → 3▸ Clic précis → 4▸ Test → 5▸ Enregistrer<br>"
            "✅ <b>CORRECTIONS:</b> Overlay non-bloquant • Countdown 6s • Zone instructions protégée • Ouverture UNIQUE"
        )
        explanation.setStyleSheet(PlatformConfigStyle.get_explanation_style())
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(explanation)

        # Layout en 2 colonnes
        columns_layout = QtWidgets.QHBoxLayout()
        columns_layout.setSpacing(20)

        # === COLONNE GAUCHE : Workflow ===
        left_column = QtWidgets.QVBoxLayout()
        left_column.setSpacing(15)

        # === Étape 1: Sélection plateforme ===
        platform_group = QtWidgets.QGroupBox("1▸ Plateforme")
        platform_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        platform_group.setMaximumWidth(320)
        platform_layout = QtWidgets.QVBoxLayout(platform_group)

        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.platform_combo.currentIndexChanged.connect(self._on_platform_selected)
        platform_layout.addWidget(self.platform_combo)

        left_column.addWidget(platform_group)

        # === Étape 2: Ouverture navigateur CORRIGÉE ===
        browser_group = QtWidgets.QGroupBox("2▸ Navigateur CORRIGÉ")
        browser_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        browser_group.setMaximumWidth(320)
        browser_layout = QtWidgets.QVBoxLayout(browser_group)

        # ✅ CORRIGÉ: Bouton avec mention overlay NON-BLOQUANT
        self.open_browser_button = QtWidgets.QPushButton("🌐 Ouvrir navigateur UNIQUE + Overlay 6s")
        self.open_browser_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.open_browser_button.clicked.connect(self._open_browser_and_start_capture)
        self.open_browser_button.setMinimumHeight(45)
        self.open_browser_button.setEnabled(False)
        browser_layout.addWidget(self.open_browser_button)

        # ✅ CORRIGÉ: Info avec corrections appliquées
        browser_info = QtWidgets.QLabel(
            "✅ <b>CORRIGÉ :</b> Ouverture navigateur UNIQUE avec overlay NON-BLOQUANT.<br>"
            "L'overlay se ferme automatiquement après 6 secondes (non-bloquant)."
        )
        browser_info.setWordWrap(True)
        browser_info.setStyleSheet("color: #2e7d32; font-size: 11px; padding: 5px; background-color: #e8f5e9; border-radius: 3px;")
        browser_layout.addWidget(browser_info)

        left_column.addWidget(browser_group)

        # === Étape 3: Test validation ===
        validation_group = QtWidgets.QGroupBox("3▸ Test de validation")
        validation_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        validation_group.setMaximumWidth(320)
        validation_layout = QtWidgets.QVBoxLayout(validation_group)

        # Bouton test validation
        self.validation_test_button = QtWidgets.QPushButton("🧪 Tester la configuration")
        self.validation_test_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.validation_test_button.clicked.connect(self._run_validation_test)
        self.validation_test_button.setMinimumHeight(45)
        self.validation_test_button.setEnabled(False)
        validation_layout.addWidget(self.validation_test_button)

        # Statut du test
        self.test_status = QtWidgets.QLabel("En attente de capture...")
        self.test_status.setAlignment(Qt.AlignCenter)
        self.test_status.setStyleSheet("color: #888; padding: 5px; font-size: 11px;")
        self.test_status.setWordWrap(True)
        validation_layout.addWidget(self.test_status)

        left_column.addWidget(validation_group)

        # === Étape 4: Enregistrement ===
        save_group = QtWidgets.QGroupBox("4▸ Enregistrement")
        save_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        save_group.setMaximumWidth(320)
        save_layout = QtWidgets.QVBoxLayout(save_group)

        # Bouton enregistrer
        self.save_button = QtWidgets.QPushButton("✅ Enregistrer la configuration")
        self.save_button.setStyleSheet(PlatformConfigStyle.get_button_style() + "font-weight: bold;")
        self.save_button.clicked.connect(self._save_configuration)
        self.save_button.setMinimumHeight(45)
        self.save_button.setEnabled(False)
        save_layout.addWidget(self.save_button)

        left_column.addWidget(save_group)

        # Statut global
        self.capture_status = QtWidgets.QLabel("💡 Sélectionnez une plateforme pour commencer")
        self.capture_status.setAlignment(Qt.AlignCenter)
        self.capture_status.setStyleSheet("color: #666; padding: 10px; background-color: #f9f9f9; border-radius: 4px;")
        self.capture_status.setWordWrap(True)
        left_column.addWidget(self.capture_status)

        left_column.addStretch()

        # === COLONNE DROITE : Configuration et Résultats ===
        right_column = QtWidgets.QVBoxLayout()

        # === Configuration de soumission ===
        submit_group = QtWidgets.QGroupBox("⌨️ Configuration de soumission")
        submit_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        submit_layout = QtWidgets.QFormLayout(submit_group)

        # Méthode de soumission
        self.submit_method_combo = QtWidgets.QComboBox()
        self.submit_method_combo.addItems([
            "Entrée simple",
            "Ctrl + Entrée", 
            "Shift + Entrée",
            "Alt + Entrée"
        ])
        self.submit_method_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        submit_layout.addRow("Méthode:", self.submit_method_combo)

        # Délai avant soumission
        self.submit_delay_spin = QtWidgets.QDoubleSpinBox()
        self.submit_delay_spin.setRange(0.1, 2.0)
        self.submit_delay_spin.setValue(0.5)
        self.submit_delay_spin.setSingleStep(0.1)
        self.submit_delay_spin.setDecimals(1)
        self.submit_delay_spin.setSuffix(" sec")
        self.submit_delay_spin.setStyleSheet(PlatformConfigStyle.get_input_style())
        submit_layout.addRow("Délai:", self.submit_delay_spin)

        # Effacement automatique
        self.auto_clear_check = QtWidgets.QCheckBox("Effacer le champ avant saisie")
        self.auto_clear_check.setChecked(True)
        submit_layout.addRow("", self.auto_clear_check)

        right_column.addWidget(submit_group)

        # === Résultats de capture CORRIGÉS ===
        result_group = QtWidgets.QGroupBox("📍 Résultats de capture (overlay NON-BLOQUANT)")
        result_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        result_layout = QtWidgets.QVBoxLayout(result_group)

        # Informations de position
        self.position_info = QtWidgets.QLabel("Aucune position capturée")
        self.position_info.setStyleSheet(
            "padding: 15px; background-color: #f8f9fa; border-radius: 4px; font-family: 'Courier New'; font-size: 11px;")
        self.position_info.setWordWrap(True)
        result_layout.addWidget(self.position_info)

        right_column.addWidget(result_group)
        right_column.addStretch()

        # === Assemblage ===
        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_column)
        left_widget.setMaximumWidth(340)

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_column)

        columns_layout.addWidget(left_widget)
        columns_layout.addWidget(right_widget, 1)

        main_layout.addLayout(columns_layout)

        # ✅ CORRIGÉ: Note finale avec corrections
        help_note = QtWidgets.QLabel(
            "✅ <b>CORRECTIONS APPLIQUÉES :</b><br>"
            "• Overlay NON-BLOQUANT (6s countdown)<br>"
            "• Zone instructions 100% protégée<br>"
            "• Ouverture navigateur UNIQUE<br>"
            "• Crosshair précis en dehors instructions"
        )
        help_note.setWordWrap(True)
        help_note.setStyleSheet("color: #2e7d32; padding: 10px; font-style: italic; font-size: 12px; background-color: #e8f5e9; border-radius: 8px;")
        help_note.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(help_note)

    # ===================================================================
    # MÉTHODES DE GESTION (identiques - préservées)
    # ===================================================================

    def set_profiles(self, profiles):
        self.profiles = profiles
        self._update_platform_combo()

    def select_platform(self, platform_name):
        index = self.platform_combo.findText(platform_name)
        if index >= 0:
            self.platform_combo.setCurrentIndex(index)

    def refresh(self):
        self._update_platform_combo()
        if self.current_platform:
            self._load_platform_config(self.current_platform)

    def _update_platform_combo(self):
        current_text = self.platform_combo.currentText()
        self.platform_combo.clear()
        self.platform_combo.addItem("-- Sélectionnez une plateforme --")
        for name in sorted(self.profiles.keys()):
            self.platform_combo.addItem(name)
        if current_text:
            index = self.platform_combo.findText(current_text)
            if index >= 0:
                self.platform_combo.setCurrentIndex(index)

    def _on_platform_selected(self, index):
        if index <= 0:
            self.current_platform = None
            self.current_profile = None
            self._reset_workflow()
            return
        platform_name = self.platform_combo.currentText()
        self._load_platform_config(platform_name)

    def _load_platform_config(self, platform_name):
        self.current_platform = platform_name
        self.current_profile = self.profiles.get(platform_name, {})

        if not self.current_profile:
            logger.debug(f"Profil vide pour {platform_name}")
            self._reset_workflow()
            return

        # Auto-configuration pour Gemini
        if platform_name.lower() == 'gemini':
            self.submit_method_combo.setCurrentIndex(1)  # Ctrl+Enter

        # Vérifier si déjà configuré
        positions = self.current_profile.get('interface_positions', {})
        if positions:
            self.captured_positions = positions.copy()
            self._update_position_display()
            
            self.field_captured = True
            self.validation_done = True
            self._update_workflow_buttons()
            
            self.capture_status.setText("✅ Configuration existante trouvée !")
            self.capture_status.setStyleSheet("color: #2e7d32; padding: 10px; background-color: #e8f5e9; border-radius: 4px;")
            self.test_status.setText("Configuration prête")
        else:
            self.captured_positions = {}
            self._reset_workflow()
            
            browser_config = self.current_profile.get('browser', {})
            window_order = browser_config.get('window_order', 1)
            
            if window_order > 1:
                status_msg = f"🎯 Étape 1 : Ouvrir navigateur (fenêtre #{window_order})"
            else:
                status_msg = "🎯 Étape 1 : Ouvrir le navigateur"
                
            self.capture_status.setText(status_msg)
            self.capture_status.setStyleSheet("color: #1976D2; padding: 10px; background-color: #e3f2fd; border-radius: 4px;")
            self.open_browser_button.setEnabled(True)

    def _reset_workflow(self):
        self.browser_opened = False
        self.field_captured = False
        self.button_captured = False
        self.validation_done = False
        
        self.captured_positions = {}
        self.capture_status.setText("💡 Sélectionnez une plateforme pour commencer")
        self.capture_status.setStyleSheet("color: #666; padding: 10px; background-color: #f9f9f9; border-radius: 4px;")
        self.position_info.setText("Aucune position capturée")
        self.test_status.setText("En attente de capture...")
        
        self._update_workflow_buttons()

    def _update_workflow_buttons(self):
        self.open_browser_button.setEnabled(not self.browser_opened and self.current_platform is not None)
        self.validation_test_button.setEnabled(self.field_captured and not self.validation_done)
        self.save_button.setEnabled(self.field_captured and self.validation_done)

    # ===================================================================
    # ✅ CORRIGÉ: WORKFLOW avec overlay NON-BLOQUANT
    # ===================================================================

    def _open_browser_and_start_capture(self):
        """✅ CORRIGÉ: Ouvrir navigateur UNIQUE avec overlay NON-BLOQUANT (6s)"""
        if not self.current_platform or not self.current_profile:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Sélectionnez d'abord une plateforme.")
            return

        try:
            browser_config = self.current_profile.get('browser', {})
            browser_type = browser_config.get('type', 'Chrome')
            browser_url = browser_config.get('url', '')
            window_order = browser_config.get('window_order', 1)
            
            logger.info(f"🌐 CORRIGÉ: Ouverture navigateur UNIQUE pour {self.current_platform}")
            logger.info(f"  - URL: {browser_url}")
            logger.info(f"  - Fenêtre: #{window_order}")

            if not browser_url:
                QtWidgets.QMessageBox.warning(self, "URL manquante", "Configurez d'abord l'URL dans l'onglet Navigateur.")
                return

            # ✅ CORRIGÉ: Avertissement overlay NON-BLOQUANT
            if window_order > 1:
                reply = QtWidgets.QMessageBox.information(
                    self,
                    "Information",
                    f"ℹ️ <b>Information :</b><br><br>"
                    f"Le système va ouvrir le navigateur pour la fenêtre #{window_order}.<br>"
                    f"L'overlay <b>NON-BLOQUANT</b> s'affichera automatiquement pendant <b>6 secondes</b>.<br><br>"
                    f"✅ <b>CORRIGÉ:</b> L'overlay ne bloquera plus votre ordinateur.<br><br>"
                    f"Continuer ?",
                    QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel
                )
                
                if reply != QtWidgets.QMessageBox.Ok:
                    return

            self.open_browser_button.setEnabled(False)
            self.capture_status.setText(f"🌐 Ouverture navigateur UNIQUE (CORRIGÉ)...")
            self.capture_status.setStyleSheet("color: #1976D2; padding: 10px; background-color: #e3f2fd; border-radius: 4px;")

            QtWidgets.QApplication.processEvents()

            # ✅ CORRIGÉ: Utiliser test_browser_only (compatible avec SimpleBrowserManager)
            result = self.conductor.test_browser_only(
                platform_name=self.current_platform,
                browser_type=browser_type,
                browser_path=browser_config.get('path', ''),
                url=browser_url,
                window_order=window_order
            )

            if result.get('success'):
                self.browser_opened = True
                
                self.capture_status.setText("✅ Navigateur ouvert ! Démarrage overlay NON-BLOQUANT (6s)...")
                self.capture_status.setStyleSheet("color: #2e7d32; padding: 10px; background-color: #e8f5e9; border-radius: 4px;")
                
                QtWidgets.QApplication.processEvents()
                time.sleep(1)
                
                # ✅ CORRIGÉ: Démarrer la capture avec overlay NON-BLOQUANT
                self._start_automatic_capture_corrected()
                
            else:
                error_msg = result.get('message', 'Erreur inconnue')
                self.capture_status.setText(f"❌ Erreur : {error_msg}")
                self.capture_status.setStyleSheet("color: #d32f2f; padding: 10px; background-color: #ffebee; border-radius: 4px;")
                QtWidgets.QMessageBox.critical(self, "Erreur", f"❌ Impossible d'ouvrir le navigateur :\n{error_msg}")
                self.open_browser_button.setEnabled(True)

        except Exception as e:
            logger.error(f"Erreur ouverture navigateur: {e}")
            self.capture_status.setText(f"❌ Erreur : {str(e)}")
            self.capture_status.setStyleSheet("color: #d32f2f; padding: 10px; background-color: #ffebee; border-radius: 4px;")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"❌ Erreur :\n{str(e)}")
            self.open_browser_button.setEnabled(True)

    def _start_automatic_capture_corrected(self):
        """✅ CORRIGÉ: Démarre la capture avec overlay NON-BLOQUANT (6s)"""
        try:
            if not HAS_CAPTURE_TOOLS:
                QtWidgets.QMessageBox.critical(self, "Erreur", "Outils de capture non disponibles.")
                return

            self.is_capturing = True
            self.current_capture_type = "field"
            
            self.capture_status.setText("🎯 OVERLAY NON-BLOQUANT ACTIF (6s) - Cliquez EN DEHORS des instructions !")
            self.capture_status.setStyleSheet("color: #ff6b00; padding: 10px; background-color: #fff3e0; border-radius: 4px; font-weight: bold;")
            
            # ✅ CORRIGÉ: Créer l'overlay NON-BLOQUANT avec countdown 6s
            self.overlay = CaptureOverlay("field")
            self.overlay.click_captured.connect(self._on_click_captured_corrected)
            self.overlay.capture_cancelled.connect(self._on_capture_cancelled_corrected)
            
            # ✅ CORRIGÉ: Afficher l'overlay NON-BLOQUANT
            self.overlay.showOverlay()
            
        except Exception as e:
            logger.error(f"Erreur capture automatique: {e}")
            self._on_capture_cancelled_corrected()

    @pyqtSlot(int, int)
    def _on_click_captured_corrected(self, x, y):
        """✅ CORRIGÉ: Callback clic capturé avec overlay NON-BLOQUANT"""
        try:
            logger.info(f"🎯 CORRIGÉ: Clic capturé en ({x}, {y}) pour {self.current_capture_type}")
            
            # Fermer l'overlay
            if self.overlay:
                self.overlay.close()
                self.overlay = None
            
            self.is_capturing = False
            
            # Créer la position capturée
            position = {
                'x': x - 50,
                'y': y - 15,
                'width': 100,
                'height': 30,
                'center_x': x,
                'center_y': y,
                'capture_method': 'user_click_overlay_non_bloquant_6s',  # ✅ CORRIGÉ
                'timestamp': time.time()
            }
            
            if self.current_capture_type == "field":
                self.captured_positions['prompt_field'] = position
                self.field_captured = True
                
                self.capture_status.setText(f"✅ Champ capturé en ({x}, {y}) avec overlay NON-BLOQUANT ! Testez maintenant.")
                self.capture_status.setStyleSheet("color: #2e7d32; padding: 10px; background-color: #e8f5e9; border-radius: 4px;")
                
                # Demander capture bouton optionnelle
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Capture du bouton",
                    f"✅ <b>Champ capturé avec overlay NON-BLOQUANT !</b><br><br>"
                    f"Capturer aussi le bouton de soumission ?<br>"
                    f"(Optionnel - vous pouvez passer au test)",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No
                )
                
                if reply == QtWidgets.QMessageBox.Yes:
                    self._start_button_capture_corrected()
                else:
                    self._finalize_capture_corrected()
                    
            elif self.current_capture_type == "button":
                self.captured_positions['submit_button'] = position
                self.button_captured = True
                
                self.capture_status.setText(f"✅ Bouton capturé en ({x}, {y}) avec overlay NON-BLOQUANT !")
                self.capture_status.setStyleSheet("color: #2e7d32; padding: 10px; background-color: #e8f5e9; border-radius: 4px;")
                
                self._finalize_capture_corrected()
            
        except Exception as e:
            logger.error(f"Erreur traitement clic: {e}")
            self._on_capture_cancelled_corrected()

    def _start_button_capture_corrected(self):
        """✅ CORRIGÉ: Capture bouton avec overlay NON-BLOQUANT (6s)"""
        try:
            self.is_capturing = True
            self.current_capture_type = "button"
            
            self.capture_status.setText("🎯 OVERLAY BOUTON NON-BLOQUANT (6s) - Cliquez EN DEHORS des instructions !")
            self.capture_status.setStyleSheet("color: #ff6b00; padding: 10px; background-color: #fff3e0; border-radius: 4px; font-weight: bold;")
            
            # ✅ CORRIGÉ: Overlay NON-BLOQUANT pour bouton
            self.overlay = CaptureOverlay("button")
            self.overlay.click_captured.connect(self._on_click_captured_corrected)
            self.overlay.capture_cancelled.connect(self._on_capture_cancelled_corrected)
            self.overlay.showOverlay()
            
        except Exception as e:
            logger.error(f"Erreur capture bouton: {e}")
            self._on_capture_cancelled_corrected()

    def _finalize_capture_corrected(self):
        """✅ CORRIGÉ: Finalise la capture"""
        self._update_position_display()
        self._update_workflow_buttons()
        
        self.test_status.setText("⚠️ Testez la configuration avant d'enregistrer")
        self.test_status.setStyleSheet("color: #ff9800;")

    @pyqtSlot()
    def _on_capture_cancelled_corrected(self):
        """✅ CORRIGÉ: Callback annulation overlay NON-BLOQUANT"""
        if self.overlay:
            self.overlay.close()
            self.overlay = None
            
        self.is_capturing = False
        self.capture_status.setText("❌ Capture annulée ou timeout (6s) - overlay NON-BLOQUANT")
        self.capture_status.setStyleSheet("color: #d32f2f; padding: 10px; background-color: #ffebee; border-radius: 4px;")
        
        self.browser_opened = False
        self._update_workflow_buttons()

    # ===================================================================
    # RESTE DES MÉTHODES (identiques - préservées)
    # ===================================================================

    def _run_validation_test(self):
        """Test de validation (PRÉSERVÉ)"""
        if 'prompt_field' not in self.captured_positions:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Aucune position capturée.")
            return
            
        try:
            self.validation_test_button.setEnabled(False)
            self.test_status.setText("🧪 Test de validation...")
            self.test_status.setStyleSheet("color: #1976D2;")
            
            position = self.captured_positions['prompt_field']
            test_text = f"Test validation - {time.strftime('%H:%M:%S')}"
            
            success = self._perform_field_test(position, test_text)
            
            if success:
                self.validation_done = True
                self.test_status.setText("✅ Test de validation réussi !")
                self.test_status.setStyleSheet("color: #2e7d32;")
                
                self.capture_status.setText("✅ Configuration validée avec overlay NON-BLOQUANT !")
                self.capture_status.setStyleSheet("color: #2e7d32; padding: 10px; background-color: #e8f5e9; border-radius: 4px;")
                
                QtWidgets.QMessageBox.information(self, "Test réussi", "✅ Test de validation réussi !")
            else:
                self.test_status.setText("❌ Test échoué")
                self.test_status.setStyleSheet("color: #d32f2f;")
                QtWidgets.QMessageBox.warning(self, "Test échoué", "❌ Le test a échoué.")
                
            self._update_workflow_buttons()
                
        except Exception as e:
            logger.error(f"Erreur test: {e}")
            self.test_status.setText("❌ Erreur test")
            self.test_status.setStyleSheet("color: #d32f2f;")
        finally:
            if not self.validation_done:
                self.validation_test_button.setEnabled(True)

    def _perform_field_test(self, position, test_text):
        """Test du champ (PRÉSERVÉ)"""
        try:
            if not HAS_CAPTURE_TOOLS:
                return False
                
            pyautogui.click(position['center_x'], position['center_y'])
            time.sleep(0.3)
            
            if self.auto_clear_check.isChecked():
                pyautogui.hotkey('ctrl', 'a')
                pyautogui.press('delete')
                time.sleep(0.2)
            
            pyautogui.typewrite(test_text)
            time.sleep(self.submit_delay_spin.value())
            
            method_index = self.submit_method_combo.currentIndex()
            if method_index == 0:
                pyautogui.press('enter')
            elif method_index == 1:
                pyautogui.hotkey('ctrl', 'enter')
            elif method_index == 2:
                pyautogui.hotkey('shift', 'enter')
            elif method_index == 3:
                pyautogui.hotkey('alt', 'enter')
                
            return True
            
        except Exception as e:
            logger.error(f"Erreur test: {e}")
            return False

    def _update_position_display(self):
        """✅ CORRIGÉ: Mise à jour affichage avec mention overlay NON-BLOQUANT"""
        if not self.captured_positions:
            self.position_info.setText("Aucune position capturée")
            return
            
        info_text = "📍 <b>Positions capturées (overlay NON-BLOQUANT 6s) :</b><br><br>"
        
        if 'prompt_field' in self.captured_positions:
            pos = self.captured_positions['prompt_field']
            info_text += f"🎯 <b>Champ :</b> ({pos['center_x']}, {pos['center_y']})<br><br>"
            
        if 'submit_button' in self.captured_positions:
            pos = self.captured_positions['submit_button']
            info_text += f"🔘 <b>Bouton :</b> ({pos['center_x']}, {pos['center_y']})<br><br>"
            
        info_text += "✅ <i>Overlay NON-BLOQUANT - Countdown 6s - Zone instructions protégée</i>"
        
        self.position_info.setText(info_text)

    def _save_configuration(self):
        """✅ CORRIGÉ: Sauvegarde avec mention overlay NON-BLOQUANT"""
        if not self.current_platform or not self.captured_positions or not self.validation_done:
            QtWidgets.QMessageBox.warning(self, "Erreur", "Test requis avant enregistrement.")
            return
            
        try:
            if 'interface_positions' not in self.current_profile:
                self.current_profile['interface_positions'] = {}
                
            self.current_profile['interface_positions'].update(self.captured_positions)
            
            if 'interface' not in self.current_profile:
                self.current_profile['interface'] = {}
                
            method_map = {0: 'enter', 1: 'ctrl_enter', 2: 'shift_enter', 3: 'alt_enter'}
            submit_method = method_map.get(self.submit_method_combo.currentIndex(), 'enter')
            
            # ✅ CORRIGÉ: Config avec mention overlay NON-BLOQUANT
            prompt_field_config = {
                "type": "captured_field_overlay_non_bloquant_6s",  # ✅ CORRIGÉ
                "detection": {
                    "method": "user_click_overlay_non_bloquant_6s",  # ✅ CORRIGÉ
                    "capture_timestamp": time.time(),
                    "validation_passed": True,
                    "overlay_corrections": "non_bloquant_6s_zone_protegee"  # ✅ CORRIGÉ
                },
                "submission": {
                    "method": submit_method,
                    "delay": self.submit_delay_spin.value(),
                    "auto_clear": self.auto_clear_check.isChecked()
                }
            }
            
            self.current_profile['interface']['prompt_field'] = prompt_field_config
            
            success = self._save_profile()
            
            if success:
                self.prompt_field_configured.emit(self.current_platform, prompt_field_config)
                
                if 'prompt_field' in self.captured_positions:
                    self.prompt_field_detected.emit(self.current_platform, self.captured_positions['prompt_field'])
                    
                if 'submit_button' in self.captured_positions:
                    self.submit_button_detected.emit(self.current_platform, self.captured_positions['submit_button'])
                
                # ✅ CORRIGÉ: Message de succès avec corrections
                QtWidgets.QMessageBox.information(
                    self, 
                    "✅ Succès", 
                    f"🎉 Configuration enregistrée !\n\n"
                    f"✅ CORRECTIONS APPLIQUÉES :\n"
                    f"• Overlay NON-BLOQUANT (6s)\n"
                    f"• Zone instructions protégée\n"
                    f"• Ouverture navigateur UNIQUE"
                )
                
                self._reset_workflow()
            else:
                QtWidgets.QMessageBox.critical(self, "Erreur", "❌ Impossible d'enregistrer.")
                
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")
            QtWidgets.QMessageBox.critical(self, "Erreur", f"Erreur: {str(e)}")

    def _save_profile(self):
        """Sauvegarde profil (PRÉSERVÉE)"""
        if not self.current_platform or not self.current_profile:
            return False

        try:
            if hasattr(self.conductor, 'database') and self.conductor.database:
                if hasattr(self.conductor.database, 'save_platform'):
                    try:
                        success = self.conductor.database.save_platform(self.current_platform, self.current_profile)
                        if success:
                            return True
                    except Exception as e:
                        logger.debug(f"Erreur DB: {e}")

            if hasattr(self.config_provider, 'save_profile'):
                try:
                    success = self.config_provider.save_profile(self.current_platform, self.current_profile)
                    if success:
                        return True
                except Exception as e:
                    logger.debug(f"Erreur ConfigProvider: {e}")

            profiles_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
            os.makedirs(profiles_dir, exist_ok=True)

            file_path = os.path.join(profiles_dir, f"{self.current_platform}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.current_profile, f, indent=2, ensure_ascii=False)

            self.profiles[self.current_platform] = self.current_profile
            return True

        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")
            return False

    def closeEvent(self, event):
        """✅ CORRIGÉ: Nettoyage avec overlay NON-BLOQUANT"""
        if self.overlay:
            self.overlay.close()
        event.accept()