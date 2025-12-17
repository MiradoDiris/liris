from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QDialogButtonBox

class FileDescriptionDialog(QDialog):
    """
    Dialog pour ajouter/modifier la description d'un fichier
    """
    def __init__(self, filename, current_description="", parent=None):
        super().__init__(parent)
        self.filename = filename
        self.description = current_description
        
        self.setWindowTitle(f"Description - {filename}")
        self.setMinimumSize(500, 300)
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialise l'interface du dialog"""
        layout = QVBoxLayout(self)
        
        # Label avec le nom du fichier
        file_label = QLabel(f"<b>Fichier:</b> {self.filename}")
        layout.addWidget(file_label)
        
        # Label pour la description
        desc_label = QLabel("Description:")
        layout.addWidget(desc_label)
        
        # Zone de texte pour la description
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Entrez la description du fichier...")
        self.text_edit.setPlainText(self.description)
        layout.addWidget(self.text_edit)
        
        # Boutons OK/Annuler
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel {
                color: #2c3e50;
                font-size: 12px;
                padding: 5px;
            }
            QTextEdit {
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
                background-color: #ffffff;
            }
            QTextEdit:focus {
                border-color: #0078d4;
            }
            QDialogButtonBox QPushButton {
                min-width: 80px;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
            QDialogButtonBox QPushButton:hover {
                background-color: #e5f3ff;
            }
        """)
    
    def get_description(self):
        """Retourne la description saisie"""
        return self.text_edit.toPlainText().strip()