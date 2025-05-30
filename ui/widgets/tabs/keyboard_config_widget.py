#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/tabs/keyboard_config_widget.py
"""

import os
import json
import traceback
import locale
import platform
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal

from utils.logger import logger
from ui.styles.platform_config_style import PlatformConfigStyle


class KeyboardConfigWidget(QtWidgets.QWidget):
    """Widget de configuration du clavier pour éviter les problèmes d'accents et Alt+Tab"""

    # Signaux
    keyboard_layout_changed = pyqtSignal(str)  # Disposition changée
    keyboard_configured = pyqtSignal(dict)  # Configuration mise à jour

    def __init__(self, config_provider, conductor, parent=None):
        """
        Initialise le widget de configuration du clavier
        """
        super().__init__(parent)

        print("KeyboardConfigWidget: Initialisation...")

        self.config_provider = config_provider
        self.conductor = conductor
        self.current_config = {}

        try:
            self._init_ui()
            self._detect_system_keyboard()
            self._load_keyboard_config()
            print("KeyboardConfigWidget: Initialisation terminée avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de KeyboardConfigWidget: {str(e)}")
            print(f"ERREUR CRITIQUE: {str(e)}")
            print(traceback.format_exc())

    def _init_ui(self):
        """Configure l'interface utilisateur du widget de clavier"""
        # Layout principal
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Explication
        explanation = QtWidgets.QLabel(
            "Configuration du clavier pour résoudre les problèmes d'accents (é, è, à, ç) "
            "et empêcher les changements de fenêtre non désirés (Alt+Tab).\n"
            "Cette configuration est globale et s'applique à toutes les plateformes d'IA."
        )
        explanation.setStyleSheet(PlatformConfigStyle.get_explanation_style())
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(explanation)

        # Layout en 2 colonnes
        columns_layout = QtWidgets.QHBoxLayout()
        columns_layout.setSpacing(20)

        # === COLONNE GAUCHE : Configuration ===
        left_column = QtWidgets.QVBoxLayout()
        left_column.setSpacing(15)

        # === Section 1: Détection du clavier ===
        detection_group = QtWidgets.QGroupBox("Disposition du clavier")
        detection_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        detection_group.setMaximumWidth(350)
        detection_layout = QtWidgets.QVBoxLayout(detection_group)

        # Résultat de la détection
        self.detected_info = QtWidgets.QLabel("Détection en cours...")
        self.detected_info.setStyleSheet(
            "font-weight: bold; color: #28a745; padding: 10px; background-color: #d4edda; border-radius: 5px;")
        self.detected_info.setWordWrap(True)
        detection_layout.addWidget(self.detected_info)

        # Option pour forcer manuellement
        manual_layout = QtWidgets.QFormLayout()

        self.keyboard_layout_combo = QtWidgets.QComboBox()
        self.keyboard_layout_combo.addItems([
            "AZERTY (Français)",
            "QWERTY (Anglais/International)",
            "Autre"
        ])
        self.keyboard_layout_combo.setStyleSheet(PlatformConfigStyle.get_input_style())
        self.keyboard_layout_combo.currentTextChanged.connect(self._on_layout_changed)
        manual_layout.addRow("Forcer manuellement:", self.keyboard_layout_combo)

        detection_layout.addLayout(manual_layout)
        left_column.addWidget(detection_group)

        # === Section 2: Configuration des accents ===
        accents_group = QtWidgets.QGroupBox("Gestion des accents")
        accents_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        accents_group.setMaximumWidth(350)
        accents_layout = QtWidgets.QVBoxLayout(accents_group)

        # Délai entre les touches
        timing_layout = QtWidgets.QFormLayout()

        self.key_delay_spin = QtWidgets.QSpinBox()
        self.key_delay_spin.setRange(0, 500)
        self.key_delay_spin.setValue(50)
        self.key_delay_spin.setSuffix(" ms")
        self.key_delay_spin.setToolTip("Délai entre chaque frappe de touche")
        timing_layout.addRow("Délai entre touches:", self.key_delay_spin)

        self.accent_delay_spin = QtWidgets.QSpinBox()
        self.accent_delay_spin.setRange(0, 1000)
        self.accent_delay_spin.setValue(100)
        self.accent_delay_spin.setSuffix(" ms")
        self.accent_delay_spin.setToolTip("Délai supplémentaire pour les accents")
        timing_layout.addRow("Délai pour accents:", self.accent_delay_spin)

        accents_layout.addLayout(timing_layout)

        # Méthode des accents (automatique selon clavier)
        self.accent_method_label = QtWidgets.QLabel("Méthode: Automatique selon clavier détecté")
        self.accent_method_label.setStyleSheet("color: #666; font-style: italic;")
        accents_layout.addWidget(self.accent_method_label)

        left_column.addWidget(accents_group)

        # === Section 3: Prévention Alt+Tab ===
        protection_group = QtWidgets.QGroupBox("Protection contre Alt+Tab")
        protection_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        protection_group.setMaximumWidth(350)
        protection_layout = QtWidgets.QVBoxLayout(protection_group)

        # Options de protection
        self.block_alt_tab_check = QtWidgets.QCheckBox("Bloquer Alt+Tab pendant la saisie")
        self.block_alt_tab_check.setChecked(True)
        self.block_alt_tab_check.setToolTip("Empêche les changements de fenêtre accidentels")
        protection_layout.addWidget(self.block_alt_tab_check)

        self.focus_lock_check = QtWidgets.QCheckBox("Maintenir le focus sur le navigateur")
        self.focus_lock_check.setChecked(True)
        self.focus_lock_check.setToolTip("Garde le focus sur la fenêtre du navigateur")
        protection_layout.addWidget(self.focus_lock_check)

        # Délai de protection
        timeout_layout = QtWidgets.QFormLayout()
        self.protection_timeout_spin = QtWidgets.QSpinBox()
        self.protection_timeout_spin.setRange(5, 300)
        self.protection_timeout_spin.setValue(30)
        self.protection_timeout_spin.setSuffix(" sec")
        self.protection_timeout_spin.setToolTip("Durée de protection après début de saisie")
        timeout_layout.addRow("Durée protection:", self.protection_timeout_spin)
        protection_layout.addLayout(timeout_layout)

        left_column.addWidget(protection_group)

        # === Section 4: Actions ===
        actions_group = QtWidgets.QGroupBox("Actions")
        actions_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        actions_group.setMaximumWidth(350)
        actions_layout = QtWidgets.QVBoxLayout(actions_group)

        # Bouton de test
        self.test_button = QtWidgets.QPushButton("🧪 Tester la configuration")
        self.test_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.test_button.clicked.connect(self._test_keyboard_config)
        actions_layout.addWidget(self.test_button)

        # Bouton de sauvegarde
        self.save_button = QtWidgets.QPushButton("💾 Enregistrer")
        self.save_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.save_button.clicked.connect(self._save_keyboard_config)
        actions_layout.addWidget(self.save_button)

        # Bouton de restauration
        self.restore_button = QtWidgets.QPushButton("🔄 Valeurs par défaut")
        self.restore_button.setStyleSheet(PlatformConfigStyle.get_button_style())
        self.restore_button.clicked.connect(self._restore_defaults)
        actions_layout.addWidget(self.restore_button)

        left_column.addWidget(actions_group)

        # Spacer pour pousser tout vers le haut
        left_column.addStretch()

        # === COLONNE DROITE : Test et Information ===
        right_column = QtWidgets.QVBoxLayout()

        # === Section Test ===
        test_group = QtWidgets.QGroupBox("Zone de test")
        test_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        test_layout = QtWidgets.QVBoxLayout(test_group)

        # Instructions
        test_info = QtWidgets.QLabel(
            "Testez votre configuration en tapant dans cette zone.\n"
            "Essayez: café, hôtel, naïf, français, piña, etc."
        )
        test_info.setWordWrap(True)
        test_info.setStyleSheet("color: #555; margin-bottom: 10px;")
        test_layout.addWidget(test_info)

        # Zone de saisie
        self.test_input = QtWidgets.QTextEdit()
        self.test_input.setPlaceholderText("Tapez ici pour tester les accents...")
        self.test_input.setStyleSheet(
            "QTextEdit { "
            "border: 2px solid #ddd; "
            "border-radius: 5px; "
            "padding: 10px; "
            "font-family: 'Courier New', monospace; "
            "font-size: 14px; "
            "background-color: #f9f9f9; "
            "}"
        )
        self.test_input.setMaximumHeight(120)
        self.test_input.textChanged.connect(self._analyze_test_input)
        test_layout.addWidget(self.test_input)

        # Résultat du test
        self.test_result = QtWidgets.QLabel("Tapez quelque chose ci-dessus...")
        self.test_result.setWordWrap(True)
        self.test_result.setStyleSheet(
            "QLabel { "
            "border: 1px solid #ccc; "
            "border-radius: 3px; "
            "padding: 8px; "
            "background-color: #fff; "
            "min-height: 40px; "
            "}"
        )
        test_layout.addWidget(self.test_result)

        right_column.addWidget(test_group)

        # === Section Configuration actuelle ===
        current_config_group = QtWidgets.QGroupBox("Configuration actuelle")
        current_config_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        current_config_layout = QtWidgets.QVBoxLayout(current_config_group)

        self.config_summary = QtWidgets.QLabel("Aucune configuration chargée")
        self.config_summary.setWordWrap(True)
        self.config_summary.setStyleSheet(
            "QLabel { "
            "font-family: 'Courier New', monospace; "
            "font-size: 11px; "
            "color: #555; "
            "background-color: #f8f9fa; "
            "border: 1px solid #e9ecef; "
            "border-radius: 3px; "
            "padding: 8px; "
            "}"
        )
        current_config_layout.addWidget(self.config_summary)

        right_column.addWidget(current_config_group)

        # === Section Information système ===
        system_info_group = QtWidgets.QGroupBox("Information système")
        system_info_group.setStyleSheet(PlatformConfigStyle.get_group_box_style())
        system_info_layout = QtWidgets.QVBoxLayout(system_info_group)

        self.system_info = QtWidgets.QLabel("Chargement...")
        self.system_info.setWordWrap(True)
        self.system_info.setStyleSheet(
            "QLabel { "
            "font-family: 'Courier New', monospace; "
            "font-size: 10px; "
            "color: #666; "
            "background-color: #f8f9fa; "
            "border: 1px solid #e9ecef; "
            "border-radius: 3px; "
            "padding: 6px; "
            "}"
        )
        system_info_layout.addWidget(self.system_info)

        right_column.addWidget(system_info_group)

        # Assembler les colonnes
        columns_layout.addLayout(left_column, 0)
        columns_layout.addLayout(right_column, 1)
        main_layout.addLayout(columns_layout)

        # Note en bas
        help_note = QtWidgets.QLabel(
            "<b>Note:</b> Cette configuration résout les problèmes de saisie d'accents "
            "et empêche les changements de fenêtre accidentels."
        )
        help_note.setWordWrap(True)
        help_note.setStyleSheet("color: #074E68; padding: 10px; font-style: italic;")
        help_note.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(help_note)

        # Mettre à jour les infos système
        self._update_system_info()

    def _detect_system_keyboard(self):
        """Détecte automatiquement la disposition du clavier"""
        try:
            # Détecter la langue du système
            language, encoding = locale.getdefaultlocale()
            system = platform.system()

            detected_layout = "QWERTY (Anglais/International)"  # Par défaut
            confidence = "Moyenne"

            if language:
                if language.startswith('fr'):
                    detected_layout = "AZERTY (Français)"
                    confidence = "Élevée"
                elif language.startswith('de') or language.startswith('ch'):
                    detected_layout = "QWERTZ (Allemand/Suisse)"
                    confidence = "Élevée"
                else:
                    confidence = "Faible"

            # Mettre à jour l'affichage
            self.detected_info.setText(
                f"✅ Détection automatique:\n"
                f"Disposition: {detected_layout}\n"
                f"Langue système: {language or 'Non détectée'}\n"
                f"Confiance: {confidence}"
            )

            # Appliquer la détection
            index = self.keyboard_layout_combo.findText(detected_layout)
            if index >= 0:
                self.keyboard_layout_combo.setCurrentIndex(index)

            # Configurer automatiquement les délais selon le clavier
            if "AZERTY" in detected_layout:
                self.key_delay_spin.setValue(30)
                self.accent_delay_spin.setValue(50)
                self.accent_method_label.setText("Méthode: Accents directs (é, è, à, ç)")
            else:
                self.key_delay_spin.setValue(50)
                self.accent_delay_spin.setValue(150)
                self.accent_method_label.setText("Méthode: Alt+codes numériques")

            logger.info(f"Clavier détecté: {detected_layout}")

        except Exception as e:
            logger.error(f"Erreur détection clavier: {str(e)}")
            self.detected_info.setText("❌ Erreur de détection. Configurez manuellement.")
            self.detected_info.setStyleSheet(
                "font-weight: bold; color: #dc3545; padding: 10px; background-color: #f8d7da; border-radius: 5px;")

    def _update_system_info(self):
        """Met à jour les informations système"""
        try:
            system = platform.system()
            version = platform.release()
            language, encoding = locale.getdefaultlocale()

            info_text = (
                f"OS: {system} {version}\n"
                f"Locale: {language or 'Non définie'}\n"
                f"Encodage: {encoding or 'Non défini'}\n"
                f"Architecture: {platform.machine()}"
            )

            self.system_info.setText(info_text)

        except Exception as e:
            self.system_info.setText(f"Erreur: {str(e)}")

    def _on_layout_changed(self):
        """Gère le changement de disposition clavier"""
        layout = self.keyboard_layout_combo.currentText()
        print(f"DEBUG: Disposition clavier changée vers: {layout}")

        # Ajuster automatiquement les paramètres
        if "AZERTY" in layout:
            self.key_delay_spin.setValue(30)
            self.accent_delay_spin.setValue(50)
            self.accent_method_label.setText("Méthode: Accents directs (é, è, à, ç)")
        else:
            self.key_delay_spin.setValue(50)
            self.accent_delay_spin.setValue(150)
            self.accent_method_label.setText("Méthode: Alt+codes numériques")

        # Mettre à jour le résumé
        self._update_config_summary()

        # Émettre le signal
        self.keyboard_layout_changed.emit(layout)

    def _analyze_test_input(self):
        """Analyse le texte saisi dans la zone de test"""
        text = self.test_input.toPlainText()
        if not text:
            self.test_result.setText("Tapez quelque chose ci-dessus...")
            self.test_result.setStyleSheet(
                "QLabel { border: 1px solid #ccc; background-color: #fff; "
                "padding: 8px; border-radius: 3px; }"
            )
            return

        # Analyser les caractères accentués
        accents_francais = "éèàçùêâîôûïüÿñ"
        accents_found = []

        for char in text:
            if char.lower() in accents_francais and char not in accents_found:
                accents_found.append(char)

        # Résultat
        if accents_found:
            result_text = f"✅ Accents détectés: {', '.join(accents_found)}\nTotal caractères: {len(text)}"
            style = (
                "QLabel { border: 1px solid #28a745; background-color: #d4edda; "
                "color: #155724; padding: 8px; border-radius: 3px; }"
            )
        else:
            result_text = f"⚠️ Aucun accent détecté\nTotal caractères: {len(text)}"
            style = (
                "QLabel { border: 1px solid #ffc107; background-color: #fff3cd; "
                "color: #856404; padding: 8px; border-radius: 3px; }"
            )

        self.test_result.setText(result_text)
        self.test_result.setStyleSheet(style)

    def _test_keyboard_config(self):
        """Lance un test de la configuration"""
        QtWidgets.QMessageBox.information(
            self,
            "Test de configuration",
            "Test à effectuer:\n\n"
            "1. Tapez dans la zone de test ci-contre\n"
            "2. Essayez des mots avec accents: café, hôtel, français\n"
            "3. Vérifiez que les accents s'affichent correctement\n"
            "4. Essayez Alt+Tab (ne devrait pas changer de fenêtre)\n\n"
            "Si les accents ne marchent pas, ajustez les délais."
        )

        # Mettre le focus sur la zone de test
        self.test_input.setFocus()

    def _get_current_config(self):
        """Récupère la configuration actuelle"""
        layout = self.keyboard_layout_combo.currentText()

        return {
            'layout': layout,
            'key_delay': self.key_delay_spin.value(),
            'accent_delay': self.accent_delay_spin.value(),
            'block_alt_tab': self.block_alt_tab_check.isChecked(),
            'focus_lock': self.focus_lock_check.isChecked(),
            'protection_timeout': self.protection_timeout_spin.value(),
            'accent_method': 'direct' if 'AZERTY' in layout else 'alt_codes'
        }

    def _update_config_summary(self):
        """Met à jour le résumé de configuration"""
        config = self._get_current_config()

        summary = (
            f"Disposition: {config['layout']}\n"
            f"Délai touches: {config['key_delay']}ms\n"
            f"Délai accents: {config['accent_delay']}ms\n"
            f"Méthode accents: {config['accent_method']}\n"
            f"Protection Alt+Tab: {'Oui' if config['block_alt_tab'] else 'Non'}\n"
            f"Verrouillage focus: {'Oui' if config['focus_lock'] else 'Non'}\n"
            f"Timeout protection: {config['protection_timeout']}s"
        )

        self.config_summary.setText(summary)

    def _save_keyboard_config(self):
        """Sauvegarde la configuration du clavier"""
        try:
            config = self._get_current_config()

            # Sauvegarder en base si disponible
            if hasattr(self.conductor, 'database') and self.conductor.database:
                success = self.conductor.database.save_keyboard_config(config)
                if success:
                    self.current_config = config
                    self._update_config_summary()

                    QtWidgets.QMessageBox.information(
                        self,
                        "Configuration sauvegardée",
                        "La configuration du clavier a été enregistrée avec succès."
                    )

                    # Émettre le signal
                    self.keyboard_configured.emit(config)
                    logger.info("Configuration clavier sauvegardée")
                    return

            # Fallback: sauvegarder en fichier
            self._save_to_file(config)
            self.current_config = config
            self._update_config_summary()

            QtWidgets.QMessageBox.information(
                self,
                "Configuration sauvegardée",
                "La configuration du clavier a été enregistrée localement."
            )

            # Émettre le signal
            self.keyboard_configured.emit(config)

        except Exception as e:
            logger.error(f"Erreur sauvegarde configuration clavier: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de sauvegarde",
                f"Impossible de sauvegarder la configuration:\n{str(e)}"
            )

    def _save_to_file(self, config):
        """Sauvegarde en fichier local"""
        try:
            config_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
            os.makedirs(config_dir, exist_ok=True)

            config_file = os.path.join(config_dir, 'keyboard_config.json')
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            logger.info(f"Configuration clavier sauvegardée dans {config_file}")

        except Exception as e:
            logger.error(f"Erreur sauvegarde fichier clavier: {str(e)}")
            raise e

    def _load_keyboard_config(self):
        """Charge la configuration du clavier"""
        try:
            config = None

            # Charger depuis la base de données
            if hasattr(self.conductor, 'database') and self.conductor.database:
                config = self.conductor.database.get_keyboard_config()

            # Fallback: charger depuis fichier
            if not config:
                config = self._load_from_file()

            if config:
                self._apply_config(config)
                self.current_config = config
                logger.info("Configuration clavier chargée")
            else:
                # Appliquer la détection automatique par défaut
                self._update_config_summary()
                logger.info("Configuration clavier par défaut appliquée")

        except Exception as e:
            logger.error(f"Erreur chargement configuration clavier: {str(e)}")

    def _load_from_file(self):
        """Charge depuis fichier local"""
        try:
            config_dir = getattr(self.config_provider, 'profiles_dir', 'config/profiles')
            config_file = os.path.join(config_dir, 'keyboard_config.json')

            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Erreur chargement fichier clavier: {str(e)}")

        return None

    def _apply_config(self, config):
        """Applique une configuration"""
        try:
            # Disposition
            layout_text = config.get('layout', 'AZERTY (Français)')
            index = self.keyboard_layout_combo.findText(layout_text)
            if index >= 0:
                self.keyboard_layout_combo.setCurrentIndex(index)

            # Délais
            self.key_delay_spin.setValue(config.get('key_delay', 50))
            self.accent_delay_spin.setValue(config.get('accent_delay', 100))

            # Options de protection
            self.block_alt_tab_check.setChecked(config.get('block_alt_tab', True))
            self.focus_lock_check.setChecked(config.get('focus_lock', True))
            self.protection_timeout_spin.setValue(config.get('protection_timeout', 30))

            # Mettre à jour le résumé
            self._update_config_summary()

        except Exception as e:
            logger.error(f"Erreur application configuration: {str(e)}")

    def _restore_defaults(self):
        """Restaure la configuration par défaut"""
        reply = QtWidgets.QMessageBox.question(
            self,
            "Restaurer les défauts",
            "Voulez-vous restaurer la configuration par défaut?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            # Relancer la détection automatique
            self._detect_system_keyboard()

            # Réinitialiser les options
            self.block_alt_tab_check.setChecked(True)
            self.focus_lock_check.setChecked(True)
            self.protection_timeout_spin.setValue(30)

            # Vider la zone de test
            self.test_input.clear()

            # Mettre à jour le résumé
            self._update_config_summary()

    def is_configured(self):
        """
        Vérifie si le clavier est configuré

        Returns:
            bool: True si configuré
        """
        return bool(self.current_config) or self.keyboard_layout_combo.currentIndex() >= 0

    def refresh(self):
        """Actualise les données du widget"""
        self._load_keyboard_config()
        self._update_system_info()
        self._update_config_summary()