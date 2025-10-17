from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, 
    QPushButton, QHBoxLayout, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QMovie
from PyQt5 import QtGui
import os


class ModernProgressDialog(QDialog):
    """
    Dialogue de progression moderne avec:
    - Barre de progression animée
    - Messages de statut
    - Log détaillé (optionnel)
    - Animation de chargement
    - Bouton d'annulation
    """
    
    cancelled = pyqtSignal()
    
    def __init__(self, title="Opération en cours", parent=None, show_log=False, cancelable=True):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(250 if not show_log else 450)
        
        self.is_cancelled = False
        self.show_log = show_log
        self.cancelable = cancelable
        
        self._init_ui()
        self._apply_modern_style()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # === Titre ===
        self.title_label = QLabel("Préparation...")
        self.title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)
        
        # === Message de statut ===
        self.status_label = QLabel("Initialisation...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        status_font = QFont()
        status_font.setPointSize(10)
        self.status_label.setFont(status_font)
        layout.addWidget(self.status_label)
        
        # === Barre de progression ===
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v/%m")
        self.progress_bar.setMinimumHeight(30)
        layout.addWidget(self.progress_bar)
        
        # === Détails (étape actuelle) ===
        self.details_label = QLabel("")
        self.details_label.setAlignment(Qt.AlignLeft)
        self.details_label.setWordWrap(True)
        details_font = QFont()
        details_font.setPointSize(9)
        details_font.setItalic(True)
        self.details_label.setFont(details_font)
        layout.addWidget(self.details_label)
        
        # === Log détaillé (optionnel) ===
        if self.show_log:
            self.log_text = QTextEdit()
            self.log_text.setReadOnly(True)
            self.log_text.setMaximumHeight(150)
            layout.addWidget(self.log_text)
        
        # === Boutons ===
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        if self.cancelable:
            self.cancel_button = QPushButton("❌ Annuler")
            self.cancel_button.setMinimumWidth(120)
            self.cancel_button.clicked.connect(self._on_cancel)
            button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
    
    def _apply_modern_style(self):
        """Applique un style moderne au dialogue."""
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
                border-radius: 10px;
            }
            QLabel {
                color: #2c3e50;
            }
            QProgressBar {
                border: 2px solid #bdc3c7;
                border-radius: 8px;
                background-color: #ecf0f1;
                text-align: center;
                font-weight: bold;
                font-size: 11px;
                color: #2c3e50;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db,
                    stop:0.5 #2980b9,
                    stop:1 #3498db
                );
                border-radius: 6px;
            }
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #bdc3c7;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Courier New', monospace;
                font-size: 9px;
                color: #2c3e50;
            }
        """)
    
    def set_title(self, title):
        """Définit le titre principal."""
        self.title_label.setText(title)
    
    def set_status(self, status):
        """Définit le message de statut."""
        self.status_label.setText(status)
    
    def set_details(self, details):
        """Définit les détails de l'étape actuelle."""
        self.details_label.setText(f"➤ {details}")
    
    def set_progress(self, value, maximum=None):
        """
        Définit la progression.
        
        Args:
            value: Valeur actuelle
            maximum: Maximum (optionnel, si None utilise la valeur existante)
        """
        if maximum is not None:
            self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)
    
    def add_log(self, message):
        """Ajoute une ligne au log (si activé)."""
        if self.show_log:
            self.log_text.append(message)
            # Auto-scroll vers le bas
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def set_indeterminate(self, indeterminate=True):
        """Active/désactive le mode indéterminé."""
        if indeterminate:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(0)  # Mode indéterminé
        else:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)
    
    def _on_cancel(self):
        """Gère l'annulation."""
        self.is_cancelled = True
        self.cancelled.emit()
        self.cancel_button.setEnabled(False)
        self.set_status("⏸️ Annulation en cours...")
    
    def finish(self, success=True, message=""):
        """
        Termine le dialogue.
        
        Args:
            success: True si succès, False si erreur
            message: Message final à afficher
        """
        if success:
            self.progress_bar.setValue(self.progress_bar.maximum())
            self.set_title("✅ Terminé avec succès")
            self.set_status(message or "Opération terminée avec succès")
            
            # Fermer automatiquement après 1 seconde
            QTimer.singleShot(1000, self.accept)
        else:
            self.set_title("❌ Erreur")
            self.set_status(message or "Une erreur s'est produite")
            
            # Changer le bouton en "Fermer"
            if self.cancelable:
                self.cancel_button.setText("Fermer")
                self.cancel_button.clicked.disconnect()
                self.cancel_button.clicked.connect(self.reject)
                self.cancel_button.setEnabled(True)


class SpinnerDialog(QDialog):
    """
    Dialogue simple avec spinner animé pour opérations indéterminées.
    """
    
    def __init__(self, message="Chargement en cours...", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Veuillez patienter")
        self.setModal(True)
        self.setFixedSize(400, 150)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Message
        self.message_label = QLabel(message)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setWordWrap(True)
        font = QFont()
        font.setPointSize(11)
        self.message_label.setFont(font)
        layout.addWidget(self.message_label)
        
        # Barre de progression indéterminée
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Indéterminé
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimumHeight(25)
        layout.addWidget(self.progress_bar)
        
        self._apply_style()
    
    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border: 2px solid #3498db;
                border-radius: 10px;
            }
            QLabel {
                color: #2c3e50;
            }
            QProgressBar {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                background-color: #ecf0f1;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db,
                    stop:1 #2980b9
                );
                border-radius: 4px;
            }
        """)
    
    def set_message(self, message):
        """Change le message affiché."""
        self.message_label.setText(message)