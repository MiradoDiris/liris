#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ui/widgets/emergency_stop_overlay.py - Bouton STOP en overlay absolu AMÉLIORÉ

Bouton d'arrêt d'urgence avec design amélioré et arrêt propre
Position fixe en haut à droite de l'écran
"""


import sys
import time
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QColor, QPainter, QBrush, QPen, QLinearGradient
from utils.logger import logger


class EmergencyStopOverlay(QtWidgets.QWidget):
    """Bouton STOP en overlay absolu sur l'écran avec design amélioré"""

    # Signal émis quand le bouton est cliqué
    emergency_stop_requested = pyqtSignal()

    def __init__(self, conductor=None, state_automation=None, parent=None):
        super().__init__(parent)
        self.conductor = conductor
        self.state_automation = state_automation
        self.is_visible = False
        self.is_stopping = False  # Nouveau flag pour éviter les double-clics

        # Animation de pulsation
        self.pulse_animation = None
        self.opacity_effect = None

        self._setup_overlay_window()
        self._create_stop_button()
        self._setup_animations()
        self._position_top_right()

        logger.info("Bouton STOP overlay amélioré créé")

    def _setup_overlay_window(self):
        """Configure la fenêtre overlay avec taille augmentée pour le nouveau padding"""
        # Flags pour overlay absolu
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |  # Toujours au-dessus
            Qt.FramelessWindowHint |  # Pas de barre de titre
            Qt.Tool |  # Ne prend pas le focus
            Qt.WindowDoesNotAcceptFocus  # N'accepte jamais le focus
        )

        # Fond semi-transparent
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Taille augmentée pour accommoder le nouveau padding
        self.setFixedSize(180, 110)  # Augmenté pour le padding supplémentaire

        # Ne pas apparaître dans la barre des tâches
        self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, True)

    def _create_stop_button(self):
        """Crée le bouton STOP avec design amélioré et padding augmenté"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)  # Augmenté les marges du layout

        # Bouton STOP principal avec padding augmenté
        self.stop_btn = QtWidgets.QPushButton("🛑 STOP")
        self.stop_btn.setFont(QFont("Arial", 14, QFont.Bold))

        # Style amélioré avec padding considérablement augmenté
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FF6666, stop:1 #FF3333);
                color: white;
                border: 4px solid #FFFFFF;
                border-radius: 12px;
                padding: 24px 32px;
                font-weight: bold;
                font-size: 16px;
                font-family: Arial, sans-serif;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
                box-shadow: 0px 4px 8px rgba(0,0,0,0.3);
                min-height: 50px;
                min-width: 120px;
                margin: 4px;
            }
            QPushButton:hover { 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FF4444, stop:1 #FF1111);
                border: 4px solid #FFFF00;
                padding: 24px 32px;
                transform: scale(1.05);
            }
            QPushButton:pressed { 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #CC0000, stop:1 #990000);
                border: 4px solid #FFFF00;
                padding: 24px 32px;
            }
        """)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        layout.addWidget(self.stop_btn)

        # Label informatif avec espacement amélioré
        self.info_label = QtWidgets.QLabel("Arrêt d'urgence")
        self.info_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.info_label.setStyleSheet("""
            color: white;
            font-size: 11px;
            font-weight: bold;
            background-color: rgba(0, 0, 0, 180);
            border-radius: 6px;
            padding: 6px 12px;
            text-align: center;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.8);
            margin-top: 4px;
        """)
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)

    def _setup_animations(self):
        """Configure les animations de pulsation"""
        # Effet d'opacité pour l'animation
        self.opacity_effect = QtWidgets.QGraphicsOpacityEffect()
        self.stop_btn.setGraphicsEffect(self.opacity_effect)

        # Animation de pulsation
        self.pulse_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.pulse_animation.setDuration(1000)  # 1 seconde
        self.pulse_animation.setStartValue(0.7)
        self.pulse_animation.setEndValue(1.0)
        self.pulse_animation.setEasingCurve(QEasingCurve.InOutSine)
        self.pulse_animation.setLoopCount(-1)  # Boucle infinie

        # Timer pour démarrer la pulsation après un délai
        self.pulse_timer = QTimer()
        self.pulse_timer.setSingleShot(True)
        self.pulse_timer.timeout.connect(self._start_pulse)

    def _start_pulse(self):
        """Démarre l'animation de pulsation"""
        if self.pulse_animation and not self.is_stopping:
            self.pulse_animation.start()

    def _stop_pulse(self):
        """Arrête l'animation de pulsation"""
        if self.pulse_animation:
            self.pulse_animation.stop()
        if self.opacity_effect:
            self.opacity_effect.setOpacity(1.0)

    def _position_top_right(self):
        """Positionne le bouton en haut à droite de l'écran"""
        # Obtenir la géométrie de l'écran principal
        screen = QtWidgets.QApplication.desktop().screenGeometry()

        # Position en haut à droite avec marge
        margin = 15
        x = screen.width() - self.width() - margin
        y = margin

        self.move(x, y)
        logger.debug(f"Bouton STOP positionné à ({x}, {y})")

    def _on_stop_clicked(self):
        """Gère le clic sur STOP avec arrêt propre"""
        if self.is_stopping:
            logger.warning("Arrêt déjà en cours, ignorer le clic")
            return

        self.is_stopping = True
        logger.warning("🛑 BOUTON STOP OVERLAY ACTIVÉ")

        # Arrêter l'animation de pulsation
        self._stop_pulse()

        # Animation visuelle de confirmation
        self._animate_stop_confirmation()

        # Exécuter l'arrêt d'urgence de manière sécurisée
        self._execute_emergency_stop_safe()

        # Émettre le signal après l'arrêt
        self.emergency_stop_requested.emit()

    def _animate_stop_confirmation(self):
        """Animation de confirmation du STOP avec padding maintenu"""
        try:
            # Changer temporairement le style pour confirmer le clic
            self.stop_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #00FF66, stop:1 #00CC44);
                    color: black;
                    border: 4px solid #FFFFFF;
                    border-radius: 12px;
                    padding: 24px 32px;
                    font-weight: bold;
                    font-size: 16px;
                    text-shadow: 1px 1px 2px rgba(255,255,255,0.8);
                    box-shadow: 0px 4px 8px rgba(0,0,0,0.3);
                    min-height: 50px;
                    min-width: 120px;
                    margin: 4px;
                }
            """)
            self.stop_btn.setText("✅ ARRÊTÉ")
            self.info_label.setText("Arrêt en cours...")
            self.info_label.setStyleSheet("""
                color: white;
                font-size: 11px;
                font-weight: bold;
                background-color: rgba(0, 150, 0, 180);
                border-radius: 6px;
                padding: 6px 12px;
                text-align: center;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.8);
                margin-top: 4px;
            """)

            # Programmer le retour au style normal après 2 secondes
            QTimer.singleShot(2000, self._reset_button_style)

        except Exception as e:
            logger.debug(f"Erreur animation: {e}")

    def _reset_button_style(self):
        """Remet le style normal du bouton avec padding correct"""
        try:
            if not self.is_stopping:  # Ne pas reset si on est en train de s'arrêter
                self.stop_btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #FF6666, stop:1 #FF3333);
                        color: white;
                        border: 4px solid #FFFFFF;
                        border-radius: 12px;
                        padding: 24px 32px;
                        font-weight: bold;
                        font-size: 16px;
                        font-family: Arial, sans-serif;
                        text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
                        box-shadow: 0px 4px 8px rgba(0,0,0,0.3);
                        min-height: 50px;
                        min-width: 120px;
                        margin: 4px;
                    }
                    QPushButton:hover { 
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #FF4444, stop:1 #FF1111);
                        border: 4px solid #FFFF00;
                        padding: 24px 32px;
                    }
                    QPushButton:pressed { 
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #CC0000, stop:1 #990000);
                        border: 4px solid #FFFF00;
                        padding: 24px 32px;
                    }
                """)
                self.stop_btn.setText("🛑 STOP")
                self.info_label.setText("Arrêt d'urgence")
                self.info_label.setStyleSheet("""
                    color: white;
                    font-size: 11px;
                    font-weight: bold;
                    background-color: rgba(0, 0, 0, 180);
                    border-radius: 6px;
                    padding: 6px 12px;
                    text-align: center;
                    text-shadow: 1px 1px 2px rgba(0,0,0,0.8);
                    margin-top: 4px;
                """)

                # Redémarrer la pulsation
                self.pulse_timer.start(2000)

            self.is_stopping = False
        except Exception as e:
            logger.debug(f"Erreur reset style: {e}")

    def _execute_emergency_stop_safe(self):
        """Exécute l'arrêt d'urgence de manière sécurisée"""
        logger.info("🚨 Début arrêt d'urgence sécurisé")

        try:
            # 1. Arrêter StateAutomation en premier
            if self.state_automation:
                try:
                    logger.info("Arrêt StateAutomation...")
                    if hasattr(self.state_automation, 'stop_automation'):
                        self.state_automation.stop_automation()
                        time.sleep(0.3)  # Pause pour terminaison
                        if hasattr(self.state_automation, 'is_automation_running'):
                            if self.state_automation.is_automation_running():
                                logger.warning("StateAutomation toujours actif après arrêt")
                        if hasattr(self.state_automation, 'force_stop'):
                            self.state_automation.force_stop = True
                    logger.info("✅ StateAutomation arrêté")
                except Exception as e:
                    logger.warning(f"Erreur arrêt StateAutomation: {e}")

            # 2. Arrêter le Conductor
            if self.conductor:
                try:
                    logger.info("Arrêt Conductor...")
                    if hasattr(self.conductor, 'emergency_stop'):
                        self.conductor.emergency_stop()
                        time.sleep(0.3)  # Pause pour terminaison
                        logger.info("✅ Conductor.emergency_stop() appelé")
                    elif hasattr(self.conductor, 'shutdown'):
                        self.conductor.shutdown()
                        time.sleep(0.3)  # Pause pour terminaison
                        logger.info("✅ Conductor.shutdown() appelé")
                    else:
                        if hasattr(self.conductor, '_shutdown'):
                            self.conductor._shutdown = True
                        if hasattr(self.conductor, 'browser_already_active'):
                            self.conductor.browser_already_active = False
                        logger.info("✅ Flags d'arrêt Conductor configurés")
                except Exception as e:
                    logger.warning(f"Erreur arrêt Conductor: {e}")

            # 3. Fermer la console si ouverte
            try:
                import pyautogui
                pyautogui.press('f12')
                logger.debug("Console fermée par overlay")
            except Exception as e:
                logger.debug(f"Erreur fermeture console (ignorée): {e}")

            logger.warning("🚨 Arrêt d'urgence sécurisé terminé")

        except Exception as e:
            logger.error(f"Erreur arrêt d'urgence sécurisé: {e}")

    # ==============================
    # API PUBLIQUE AMÉLIORÉE
    # ==============================

    def show_overlay(self):
        """Affiche le bouton overlay avec animation"""
        if not self.is_visible:
            self._position_top_right()  # Re-calculer position
            self.show()
            self.raise_()  # S'assurer qu'il est au-dessus
            self.activateWindow()
            self.is_visible = True

            # Démarrer la pulsation après 3 secondes
            self.pulse_timer.start(3000)

            logger.info("🛑 Bouton STOP overlay affiché avec animation")

    def hide_overlay(self):
        """Cache le bouton overlay et arrête les animations"""
        if self.is_visible:
            self._stop_pulse()
            self.pulse_timer.stop()
            self.hide()
            self.is_visible = False
            logger.info("Bouton STOP overlay caché")

    def update_references(self, conductor=None, state_automation=None):
        """Met à jour les références pour l'arrêt d'urgence"""
        if conductor:
            self.conductor = conductor
            logger.debug("Référence conductor mise à jour")
        if state_automation:
            self.state_automation = state_automation
            logger.debug("Référence state_automation mise à jour")

    def is_overlay_visible(self):
        """Retourne si l'overlay est visible"""
        return self.is_visible

    # ==============================
    # ÉVÉNEMENTS SYSTÈME AMÉLIORÉS
    # ==============================

    def paintEvent(self, event):
        """Dessine un fond semi-transparent avec effet de glow"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Fond semi-transparent arrondi avec gradient
        rect = self.rect()

        # Gradient pour l'effet de profondeur
        gradient = QLinearGradient(0, 0, 0, rect.height())
        gradient.setColorAt(0, QColor(0, 0, 0, 120))
        gradient.setColorAt(1, QColor(0, 0, 0, 160))

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(255, 255, 255, 220), 3))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 12, 12)

    def mousePressEvent(self, event):
        """Gère le clic pour déplacer le bouton"""
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.globalPos()

    def mouseMoveEvent(self, event):
        """Permet de déplacer le bouton overlay"""
        if hasattr(self, 'drag_start_position'):
            if event.buttons() == Qt.LeftButton:
                # Calculer la nouvelle position
                diff = event.globalPos() - self.drag_start_position
                new_pos = self.pos() + diff

                # Limiter aux bords de l'écran
                screen = QtWidgets.QApplication.desktop().screenGeometry()
                new_x = max(0, min(new_pos.x(), screen.width() - self.width()))
                new_y = max(0, min(new_pos.y(), screen.height() - self.height()))

                self.move(new_x, new_y)
                self.drag_start_position = event.globalPos()

    def closeEvent(self, event):
        """Empêche la fermeture accidentelle et nettoie les animations"""
        event.ignore()  # Ignore la fermeture
        self.hide_overlay()


# ==============================
# EXEMPLE D'UTILISATION AMÉLIORÉ
# ==============================

def demo_emergency_overlay():
    """Démo du bouton STOP overlay amélioré"""
    app = QtWidgets.QApplication(sys.argv)

    # Créer le bouton overlay
    overlay = EmergencyStopOverlay()

    # Connecter le signal
    def on_emergency_stop():
        print("🛑 ARRÊT D'URGENCE ACTIVÉ !")
        QtWidgets.QMessageBox.information(None, "STOP",
                                          "Arrêt d'urgence activé depuis l'overlay amélioré !\n\n"
                                          "Le système a été arrêté proprement.")

    overlay.emergency_stop_requested.connect(on_emergency_stop)

    # Afficher l'overlay
    overlay.show_overlay()

    # Fenêtre principale pour tester
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle("Test avec bouton STOP overlay amélioré")
    main_window.resize(800, 500)

    central = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(central)

    # Titre
    title = QtWidgets.QLabel("Test du Bouton STOP Amélioré")
    title.setFont(QFont("Arial", 18, QFont.Bold))
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet("color: #333; margin: 20px;")
    layout.addWidget(title)

    # Informations
    info = QtWidgets.QLabel(
        "• Le bouton STOP est en haut à droite de l'écran\n"
        "• Il pulse pour attirer l'attention\n"
        "• Design amélioré avec meilleur contraste\n"
        "• Arrêt sécurisé du conductor\n"
        "• Vous pouvez le déplacer en cliquant-glissant\n"
        "• Padding augmenté pour meilleure lisibilité"
    )
    info.setFont(QFont("Arial", 12))
    info.setStyleSheet("color: #555; padding: 20px; background: #f0f0f0; border-radius: 8px;")
    layout.addWidget(info)

    # Boutons de contrôle
    controls_layout = QtWidgets.QHBoxLayout()

    toggle_btn = QtWidgets.QPushButton("Masquer/Afficher bouton STOP")
    toggle_btn.setFont(QFont("Arial", 12))
    toggle_btn.setStyleSheet("""
        QPushButton {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            font-weight: bold;
        }
        QPushButton:hover {
            background: #45a049;
        }
    """)
    toggle_btn.clicked.connect(
        lambda: overlay.hide_overlay() if overlay.is_overlay_visible() else overlay.show_overlay())
    controls_layout.addWidget(toggle_btn)

    layout.addLayout(controls_layout)
    layout.addStretch()

    main_window.setCentralWidget(central)
    main_window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    demo_emergency_overlay()