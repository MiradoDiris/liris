#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Liris/ui/widgets/language_selector.py
"""

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QComboBox, QDialogButtonBox, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QIcon
from ui.localization.translator import translator
from ui.styles.theme import Theme
import os
import sys


def get_resource_path(relative_path):
    """Obtient le chemin absolu vers une ressource"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class LanguageSelector(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Sélection de la langue")
        self.setMinimumSize(400, 300)
        
        # Appliquer le style seulement si Theme est disponible
        try:
            self.setStyleSheet(Theme.get_global_stylesheet())
        except:
            print("DEBUG: Impossible de charger le thème")
            pass

        # Layout principal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # En-tête avec logo
        header_layout = QHBoxLayout()
        logo_path = get_resource_path(os.path.join("ui", "resources", "icons", "logo.png"))
        
        if os.path.exists(logo_path):
            logo_label = QLabel()
            pixmap = QPixmap(logo_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
            header_layout.addWidget(logo_label)
        else:
            print(f"Logo non trouvé: {logo_path}")
            logo_label = QLabel("Liris")
            try:
                logo_label.setStyleSheet(f"""
                    font-size: 24px;
                    font-weight: bold;
                    color: {Theme.PRIMARY_COLOR};
                """)
            except:
                logo_label.setStyleSheet("font-size: 24px; font-weight: bold;")
            header_layout.addWidget(logo_label)

        title_label = QLabel("Bienvenue dans Liris")
        try:
            title_label.setStyleSheet(f"""
                font-size: {Theme.FONT_SIZE_TITLE}px;
                font-weight: bold;
                color: {Theme.PRIMARY_COLOR};
            """)
        except:
            title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Description
        self.desc_label = QLabel("Veuillez choisir votre langue :")
        try:
            self.desc_label.setStyleSheet(f"""
                font-size: {Theme.FONT_SIZE_NORMAL}px;
                color: {Theme.TEXT_COLOR};
            """)
        except:
            self.desc_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.desc_label)

        # ComboBox pour les langues avec drapeaux
        self.language_combo = QComboBox()
        try:
            self.language_combo.setStyleSheet(f"""
                QComboBox {{
                    font-size: {Theme.FONT_SIZE_NORMAL}px;
                    padding: 8px;
                    border: 1px solid {Theme.ACCENT_COLOR};
                    border-radius: 4px;
                    background-color: white;
                }}
                QComboBox::drop-down {{
                    border: none;
                }}
                QComboBox::down-arrow {{
                    width: 12px;
                    height: 12px;
                }}
            """)
        except:
            self.language_combo.setStyleSheet("""
                QComboBox {
                    font-size: 14px;
                    padding: 8px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                }
            """)

        # Dictionnaire associant les codes de langue aux chemins des drapeaux
        flag_mapping = {
            'fr': 'fr.png',
            'en': 'gb.png',
            'es': 'es.png',
            'de': 'de.png',
            'it': 'it.png',
            'pt': 'pt.png',
            'nl': 'nl.png',
            'ru': 'ru.png',
            'ja': 'jp.png',
            'zh': 'cn.png',
        }

        # Ajouter les langues avec les drapeaux
        for lang_code, lang_name in translator.get_available_languages().items():
            icon = None
            if lang_code in flag_mapping:
                flag_path = get_resource_path(
                    os.path.join("ui", "resources", "flags", flag_mapping[lang_code])
                )
                
                if os.path.exists(flag_path):
                    print(f"Chargement du drapeau : {flag_path}")
                    flag_icon = QIcon(flag_path)
                    icon = flag_icon
                else:
                    print(f"Drapeau non trouvé : {flag_path}")

            if icon:
                self.language_combo.addItem(icon, lang_name, lang_code)
            else:
                # Fallback sans icône si le drapeau n'est pas trouvé
                self.language_combo.addItem(lang_name, lang_code)

        # Activer l'affichage des icônes dans la liste déroulante
        self.language_combo.setIconSize(QSize(24, 16))

        layout.addWidget(self.language_combo)

        # Boutons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        try:
            self.button_box.setStyleSheet(f"""
                QPushButton {{
                    font-size: {Theme.FONT_SIZE_NORMAL}px;
                    padding: 8px 16px;
                    border-radius: 4px;
                    background-color: {Theme.PRIMARY_COLOR};
                    color: white;
                }}
                QPushButton:hover {{
                    background-color: {Theme.SECONDARY_COLOR};
                }}
            """)
        except:
            self.button_box.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    padding: 8px 16px;
                    border-radius: 4px;
                }
            """)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        layout.addStretch()

        # Définir l'icône de la fenêtre
        window_icon_path = get_resource_path(
            os.path.join("ui", "resources", "icons", "logo.png")
        )
        
        if os.path.exists(window_icon_path):
            self.setWindowIcon(QIcon(window_icon_path))
        
        print("DEBUG: LanguageSelector.__init__() terminé avec succès")

    def get_selected_language(self):
        return self.language_combo.currentData()

    def update_language(self):
        """Met à jour les textes en cas de changement de langue"""
        self.setWindowTitle(translator.translate("select_language"))
        self.desc_label.setText(translator.translate("select_language"))


# Test si le module peut être importé
if __name__ == "__main__":
    print("Module language_selector.py chargé avec succès")
    print(f"Classe LanguageSelector disponible: {LanguageSelector}")