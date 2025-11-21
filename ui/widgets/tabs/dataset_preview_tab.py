#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import os
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt

from ui.localization.translator import tr
from ui.styles.theme import Theme

logger = logging.getLogger(__name__)


class DatasetPreviewTab(QtWidgets.QWidget):
    """Dataset preview tab with configuration"""

    def __init__(self, project_manager, config_data, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self.config_data = config_data
        self._init_ui()

    def _init_ui(self):
        """Create dataset preview tab"""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # Preview (left) - 60%
        preview_frame = self._create_preview_frame()
        preview_frame.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        layout.addWidget(preview_frame, 6)

        # Configuration (right) - 40%
        config_frame = self._create_dataset_config_frame()
        config_frame.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        layout.addWidget(config_frame, 4)

    def _create_preview_frame(self):
        """Create preview panel"""
        frame = QtWidgets.QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 2px solid #e1e4e8;
            }
        """)

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        title = QtWidgets.QLabel(tr("dataset.preview_title"))
        title.setStyleSheet("font-weight: 600; font-size: 16px; color: #2c3e50;")
        layout.addWidget(title)

        # Project selection
        select_layout = QtWidgets.QHBoxLayout()
        select_layout.addWidget(QtWidgets.QLabel(tr("dataset.select_project") + ":"))
        
        self.preview_combo = QtWidgets.QComboBox()
        self.preview_combo.setStyleSheet(self._get_modern_input_style())
        self.preview_combo.currentIndexChanged.connect(self._on_preview_changed)
        select_layout.addWidget(self.preview_combo, 1)
        layout.addLayout(select_layout)

        # Preview view
        self.preview_view = QtWidgets.QTextEdit()
        self.preview_view.setReadOnly(True)
        self.preview_view.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 2px solid #e1e4e8;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        layout.addWidget(self.preview_view, 1)

        return frame

    def _create_dataset_config_frame(self):
        """Create dataset configuration panel"""
        frame = QtWidgets.QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 2px solid #e1e4e8;
            }
        """)

        layout = QtWidgets.QVBoxLayout(frame)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        title = QtWidgets.QLabel("⚙️ " + tr("dataset.tab_config"))
        title.setStyleSheet("font-weight: 600; font-size: 16px; color: #2c3e50;")
        layout.addWidget(title)

        # Platform
        layout.addWidget(self._create_field_label(tr("dataset.platform")))
        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.setStyleSheet(self._get_modern_input_style())
        self.platform_combo.addItems(["ChatGPT", "Jupyter", "Google Colab", "Kaggle", "Other"])
        self.platform_combo.currentIndexChanged.connect(self._update_config_preview)
        layout.addWidget(self.platform_combo)

        # Description
        layout.addWidget(self._create_field_label(tr("dataset.description")))
        self.description_edit = QtWidgets.QTextEdit()
        self.description_edit.setPlaceholderText(tr("dataset.description_placeholder"))
        self.description_edit.setStyleSheet("""
            QTextEdit {
                border: 2px solid #e1e4e8;
                border-radius: 6px;
                padding: 8px;
                background-color: white;
                font-size: 13px;
            }
        """)
        self.description_edit.setMaximumHeight(80)
        self.description_edit.textChanged.connect(self._update_config_preview)
        layout.addWidget(self.description_edit)

        # Format
        layout.addWidget(self._create_field_label(tr("dataset.output_format")))
        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.setStyleSheet(self._get_modern_input_style())
        self.format_combo.addItems(["JSON", "CSV", "Parquet"])
        self.format_combo.currentIndexChanged.connect(self._update_config_preview)
        layout.addWidget(self.format_combo)

        # Samples
        layout.addWidget(self._create_field_label(tr("dataset.sample_count")))
        self.samples_spin = QtWidgets.QSpinBox()
        self.samples_spin.setStyleSheet(self._get_modern_input_style())
        self.samples_spin.setRange(1, 1000000)
        self.samples_spin.setValue(100)
        self.samples_spin.valueChanged.connect(self._update_config_preview)
        layout.addWidget(self.samples_spin)

        # Technique
        layout.addWidget(self._create_field_label(tr("dataset.training_technique")))
        self.technique_combo = QtWidgets.QComboBox()
        self.technique_combo.setStyleSheet(self._get_modern_input_style())
        self.technique_combo.addItems(["Full SFT", "RLHF", "Fine-tuning"])
        self.technique_combo.currentIndexChanged.connect(self._update_config_preview)
        layout.addWidget(self.technique_combo)

        layout.addStretch()

        # Generate button
        generate_btn = QtWidgets.QPushButton(tr("dataset.generate"))
        generate_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {Theme.SECONDARY_COLOR}, stop:1 #2980b9);
                color: white;
                font-weight: 600;
                padding: 12px;
                border-radius: 6px;
                border: none;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2980b9, stop:1 {Theme.SECONDARY_COLOR});
            }}
        """)
        layout.addWidget(generate_btn)

        return frame

    def _create_field_label(self, text):
        """Create field label"""
        label = QtWidgets.QLabel(text)
        label.setStyleSheet("font-weight: 600; color: #2c3e50; font-size: 12px;")
        return label

    def _get_modern_input_style(self):
        """Modern input field style with correct dropdown icon"""
        svg_path = self._get_dropdown_svg_path()
        
        return f"""
            QLineEdit, QComboBox, QSpinBox {{
                border: 2px solid #e1e4e8;
                border-radius: 6px;
                padding: 8px 12px;
                background-color: white;
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border: 2px solid #3498db;
            }}
            QComboBox {{
                min-height: 35px;
                padding-left: 12px;
                padding-right: 35px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 32px;
                border: none;
                border-left: 1px solid #e1e4e8;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background: linear-gradient(to bottom, #fafafa, #f5f5f5);
            }}
            QComboBox::down-arrow {{
                image: url({svg_path});
                width: 18px;
                height: 18px;
            }}
            QComboBox::down-arrow:hover {{
                image: url({svg_path});
            }}
            QComboBox:disabled::down-arrow {{
                opacity: 0.5;
            }}
            QSpinBox {{
                min-height: 35px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 20px;
                border: none;
                background: #f5f5f5;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background: #e1e4e8;
            }}
        """
    
    def _get_dropdown_svg_path(self):
        """Get absolute path to dropdown SVG icon"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_dir = os.path.dirname(current_dir)
        svg_path = os.path.join(ui_dir, "resources", "icons", "dropdown.svg")
        svg_path = os.path.normpath(svg_path)
        svg_path = svg_path.replace('\\', '/')
        return svg_path

    def _on_preview_changed(self, index):
        """Handle preview change"""
        if index <= 0:
            self.preview_view.setHtml(f"<p style='text-align:center; color:#999;'>{tr('dataset.select_project_preview')}</p>")
            return
        
        project_name = self.preview_combo.currentText()
        project_data = self.project_manager.db.get_dataset_projet(project_name)
        if project_data:
            self._update_preview_html(project_data)

    def _update_config_preview(self):
        """Update configuration and refresh preview"""
        # Update config data
        self.config_data['platform'] = self.platform_combo.currentText()
        self.config_data['description'] = self.description_edit.toPlainText().strip()
        self.config_data['output_format'] = self.format_combo.currentText()
        self.config_data['sample_count'] = self.samples_spin.value()
        self.config_data['training_technique'] = self.technique_combo.currentText()

        # Refresh preview if project selected
        if self.preview_combo.currentIndex() > 0:
            self._on_preview_changed(self.preview_combo.currentIndex())

    def _update_preview_html(self, project_data):
        """Generate and display preview HTML"""
        if not project_data:
            self.preview_view.setHtml(f"<p style='text-align:center; color:#999;'>{tr('dataset.no_project_loaded')}</p>")
            return

        project_name = project_data.get('nom', 'Unnamed')
        description = project_data.get('description', '')

        html = f"""
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 15px; background: white; }}
            h2 {{ color: #2c3e50; text-align: center; border-bottom: 3px solid #3498db; padding-bottom: 12px; margin-bottom: 20px; }}
            h3 {{ color: #27ae60; margin-top: 25px; font-size: 18px; }}
            .description {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
            ul {{ list-style-type: none; padding-left: 25px; }}
            li {{ margin: 8px 0; padding: 5px; }}
            .typologie {{ color: #27ae60; font-weight: 700; font-size: 15px; }}
            .root {{ color: #e74c3c; font-weight: 600; }}
            .parent {{ color: #3498db; font-weight: 500; }}
            .child {{ color: #f39c12; }}
            .category {{ color: #95a5a6; font-size: 11px; font-style: italic; background: #ecf0f1; padding: 2px 6px; border-radius: 3px; }}
            .stats {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 15px; border-radius: 8px; margin: 20px 0; text-align: center; font-size: 16px; font-weight: 600; }}
            .config {{ background: #ffffff; border: 2px solid #e1e4e8; padding: 15px; border-radius: 8px; margin-top: 25px; }}
            .config h4 {{ color: #3498db; margin: 0 0 12px 0; border-bottom: 2px solid #3498db; padding-bottom: 8px; }}
            .config ul {{ padding-left: 0; }}
            .config li {{ padding: 6px 0; border-bottom: 1px solid #f0f0f0; }}
            .config li:last-child {{ border-bottom: none; }}
        </style>
        <h2>📊 {project_name}</h2>
        """

        if description:
            html += f'<div class="description"><strong>📝 {tr("dataset.description")}:</strong> {description}</div>'

        total_themes = 0
        typologies = project_data.get('typologies', [])

        if typologies:
            html += f'<h3>🏷️ {tr("dataset.typologies")} ({len(typologies)})</h3><ul>'
            
            for typologie in typologies:
                typ_name = typologie.get('name', 'Unnamed')
                root_labels = typologie.get('root_labels', [])
                
                html += f'<li class="typologie">📂 {typ_name}'
                
                if root_labels:
                    html += '<ul>'
                    for root in root_labels:
                        root_name = root.get('name', 'Unnamed')
                        root_cat = root.get('category', 'default')
                        parent_labels = root.get('parent_labels', [])
                        
                        html += f'<li class="root">🔹 {root_name} <span class="category">{root_cat}</span>'
                        
                        if parent_labels:
                            html += '<ul>'
                            for parent in parent_labels:
                                parent_name = parent.get('name', 'Unnamed')
                                parent_cat = parent.get('category', 'default')
                                child_labels = parent.get('child_labels', [])
                                
                                html += f'<li class="parent">🔸 {parent_name} <span class="category">{parent_cat}</span>'
                                
                                if child_labels:
                                    html += '<ul>'
                                    for child in child_labels:
                                        child_name = child.get('name', 'Unnamed')
                                        child_cat = child.get('category', 'default')
                                        total_themes += 1
                                        html += f'<li class="child">🔻 {child_name} <span class="category">{child_cat}</span></li>'
                                    html += '</ul>'
                                else:
                                    total_themes += 1
                                
                                html += '</li>'
                            html += '</ul>'
                        else:
                            total_themes += 1
                        
                        html += '</li>'
                    html += '</ul>'
                else:
                    html += f'<p style="color:#95a5a6; margin-left:25px; font-style:italic;">{tr("dataset.no_root_labels")}</p>'
                
                html += '</li>'
            
            html += '</ul>'
            
            html += f'<div class="stats">📈 {tr("dataset.total_themes")}: {total_themes}</div>'
        else:
            html += f'<div style="background:#fff3cd; padding:20px; border-radius:8px; text-align:center; border: 2px solid #ffc107;">⚠️ {tr("dataset.no_typologie_defined")}</div>'

        # Configuration section
        html += f'''
        <div class="config">
            <h4>🛠️ {tr("dataset.dataset_configuration")}</h4>
            <ul>
                <li><strong>{tr("dataset.platform")}:</strong> {self.config_data['platform']}</li>
                <li><strong>{tr("dataset.description")}:</strong> {self.config_data['description'] or tr("dataset.none")}</li>
                <li><strong>{tr("dataset.format")}:</strong> {self.config_data['output_format']}</li>
                <li><strong>{tr("dataset.samples")}:</strong> {self.config_data['sample_count']:,}</li>
                <li><strong>{tr("dataset.technique")}:</strong> {self.config_data['training_technique']}</li>
            </ul>
        </div>
        '''

        self.preview_view.setHtml(html)

    def refresh_projects(self):
        """Refresh project list in combo"""
        projects = self.project_manager.get_all_projects()
        project_names = sorted([p['name'] for p in projects])

        self.preview_combo.blockSignals(True)
        self.preview_combo.clear()
        self.preview_combo.addItem(f"-- {tr('dataset.select_project_preview')} --")
        self.preview_combo.addItems(project_names)
        
        # Select current project if exists
        if self.project_manager.current_project_name in project_names:
            index = project_names.index(self.project_manager.current_project_name) + 1
            self.preview_combo.setCurrentIndex(index)
        
        self.preview_combo.blockSignals(False)
        
        # Trigger preview update if project selected
        if self.preview_combo.currentIndex() > 0:
            self._on_preview_changed(self.preview_combo.currentIndex())

    def update_preview(self, project_data):
        """Update preview with project data"""
        self._update_preview_html(project_data)