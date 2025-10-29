import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor, QColor, QTextCharFormat, QFont
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QPushButton, QHBoxLayout
from PyQt5.QtWidgets import QApplication
from PyQt5 import QtWidgets


class CodeDialogs:
    """Utility class for displaying code snippets and file contents in dialogs."""

    def __init__(self, parent=None):
        self.parent = parent

    def _show_code_snippet_dialog(self, filename: str, full_content: str, item_type: str, line_num: int, item_text: str):
        """Affiche une fenêtre contenant un extrait de code centré sur une ligne donnée."""
        dialog = QDialog(self.parent)
        dialog.setWindowTitle(f"Snippet — {item_text}")
        dialog.setMinimumSize(1000, 600)
        dialog.setMaximumSize(1400, 900)

        # --- Palette de couleurs gris/blanc ---
        stylesheet = """
            QDialog {
                background-color: #f8f8f8;
                color: #1a1a1a;
            }
            QLabel {
                color: #1a1a1a;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #d0d0d0;
                color: #1a1a1a;
                padding: 8px 16px;
                border-radius: 6px;
                border: 1px solid #b0b0b0;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #c0c0c0;
                border: 1px solid #a0a0a0;
            }
            QPushButton:pressed {
                background-color: #b0b0b0;
            }
            QPlainTextEdit {
                font-family: 'Fira Code', 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
                background-color: #ffffff;
                color: #1a1a1a;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                padding: 12px;
                line-height: 1.5;
            }
            QScrollBar:vertical {
                background: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #b0b0b0;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #888888;
            }
        """
        dialog.setStyleSheet(stylesheet)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title_label = QLabel(f"<b style='font-size: 13pt; color: #1a1a1a'>{item_text}</b>")
        layout.addWidget(title_label)

        info_parts = [
            f"<span style='color: #333333'><b>Type :</b></span> <span style='color: #555555'>{item_type.capitalize()}</span>",
            f"<span style='color: #333333'><b>Fichier :</b></span> <span style='color: #555555; font-family: monospace'>{os.path.basename(filename)}</span>",
            f"<span style='color: #333333'><b>Ligne :</b></span> <span style='color: #555555'>{line_num}</span>"
        ]
        info_label = QLabel(" • ".join(info_parts))
        info_label.setStyleSheet("""
            QLabel {
                background-color: #e8e8e8;
                border-left: 3px solid #2a2a2a;
                border-radius: 4px;
                padding: 10px 12px;
                color: #333333;
                font-size: 9pt;
            }
        """)
        layout.addWidget(info_label)

        code_editor = QPlainTextEdit()
        code_editor.setReadOnly(True)

        lines = full_content.splitlines()
        snippet_start = max(0, line_num - 11)
        snippet_end = min(len(lines), line_num + 10)
        snippet_lines = lines[snippet_start:snippet_end]

        numbered_lines = []
        for i, line_content in enumerate(snippet_lines):
            actual_line_num = snippet_start + i + 1
            numbered_lines.append(f"{actual_line_num:4d} │ {line_content}")

        snippet = "\n".join(numbered_lines)
        if snippet_start > 0:
            snippet = f"     │ ... (lignes omises avant)\n{snippet}"
        if snippet_end < len(lines):
            snippet += f"\n     │ ... (lignes omises après)"

        code_editor.setPlainText(snippet)
        layout.addWidget(code_editor)

        cursor = code_editor.textCursor()
        target_line = line_num - snippet_start
        if snippet_start > 0:
            target_line += 1
        for _ in range(target_line):
            cursor.movePosition(QTextCursor.Down)
        cursor.select(QTextCursor.LineUnderCursor)

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#f0f0f0"))
        fmt.setForeground(QColor("#1a1a1a"))
        cursor.mergeCharFormat(fmt)
        code_editor.setTextCursor(cursor)
        code_editor.ensureCursorVisible()

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.setContentsMargins(0, 8, 0, 0)

        copy_button = QPushButton("📋 Copier le code")
        copy_button.setMinimumHeight(36)
        copy_button.clicked.connect(lambda: self._copy_to_clipboard(snippet))
        button_layout.addWidget(copy_button)

        full_button = QPushButton("📄 Fichier complet")
        full_button.setMinimumHeight(36)
        full_button.clicked.connect(lambda: self._show_file_content_dialog(filename, full_content, {'label': item_text, 'type': item_type, 'line': line_num}))
        button_layout.addWidget(full_button)

        button_layout.addStretch()

        close_button = QPushButton("✕ Fermer")
        close_button.setMinimumHeight(36)
        close_button.setMaximumWidth(120)
        close_button.clicked.connect(dialog.close)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)
        dialog.exec_()

    def _show_file_content_dialog(self, filename: str, content: str, label: dict):
        """Affiche le contenu complet du fichier dans une fenêtre élégante."""
        dialog = QDialog(self.parent)
        dialog.setWindowTitle(f"Fichier complet — {os.path.basename(filename)}")
        dialog.setMinimumSize(1200, 700)

        stylesheet = """
            QDialog {
                background-color: #f8f8f8;
                color: #1a1a1a;
            }
            QLabel {
                color: #1a1a1a;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #d0d0d0;
                color: #1a1a1a;
                padding: 8px 16px;
                border-radius: 6px;
                border: 1px solid #b0b0b0;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #c0c0c0;
                border: 1px solid #a0a0a0;
            }
            QPushButton:pressed {
                background-color: #b0b0b0;
            }
        """
        dialog.setStyleSheet(stylesheet)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title_label = QLabel(f"<b style='font-size: 13pt; color: #1a1a1a'>{label.get('label', 'Fichier')}</b>")
        layout.addWidget(title_label)

        info_parts = [
            f"<b>Fichier :</b> {os.path.basename(filename)}",
            f"<b>Type :</b> {label.get('type', 'N/A').capitalize()}",
            f"<b>Lignes totales :</b> {len(content.splitlines())}"
        ]
        file_info = QLabel(" • ".join(info_parts))
        layout.addWidget(file_info)

        code_editor = QPlainTextEdit()
        code_editor.setReadOnly(True)

        lines = content.splitlines()
        numbered_lines = [f"{i+1:5d} │ {line}" for i, line in enumerate(lines)]
        code_editor.setPlainText("\n".join(numbered_lines))
        layout.addWidget(code_editor)

        button_layout = QHBoxLayout()
        copy_all_button = QPushButton("📋 Copier tout")
        copy_all_button.clicked.connect(lambda: self._copy_to_clipboard(content))
        button_layout.addWidget(copy_all_button)

        button_layout.addStretch()

        close_button = QPushButton("✕ Fermer")
        close_button.clicked.connect(dialog.close)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)
        dialog.exec_()

    def _copy_to_clipboard(self, text: str):
        """Copie le texte dans le presse-papier."""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)
        QtWidgets.QMessageBox.information(
            self.parent,
            "Copié",
            "Contenu copié dans le presse-papier."
        )
