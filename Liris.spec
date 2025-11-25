# -*- mode: utf-8 -*-
import os
block_cipher = None

# Collecter tous les fichiers de données nécessaires
datas = [
    ('ui/localization/translations/*.json', 'ui/localization/translations'),
    ('ui/resources/icons/*', 'ui/resources/icons'),
    ('ui/resources/flags/*', 'ui/resources/flags'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'pydgraph',
        'grpc',
        'google.protobuf',
        'grpc._cython.cygrpc',
        
        # PyQt5
        'PyQt5.QtCore',
        'PyQt5.QtWidgets',
        'PyQt5.QtGui',
        'PyQt5.Qsci',
        
        # Autres dépendances
        'qtawesome',
        'requests',
        'pyperclip',
        
        # Utils
        'utils.logger',
        'utils.dgraph_connector',
        'utils.project_storage_manager',
        'utils.dgraph_project_manager',
        'utils.multi_language_parser',
        'utils.complete_call_resolver',
        
        # UI widgets
        'ui.widgets.tabs.project_config_widget',
        'ui.widgets.tabs.coding_panel',
        'ui.widgets.tabs.relations_graph_widget',
        'ui.widgets.tabs.relations_config',
        'ui.widgets.dialogs.code_dialogs',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# MODE ONEFILE : Tout dans un seul .exe
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,      # Ajouté
    a.zipfiles,      # Ajouté
    a.datas,         # Ajouté
    [],
    name='Liris',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ui/resources/icons/logo.ico' if os.path.exists('ui/resources/icons/logo.ico') else None,
    version='file_version.txt' if os.path.exists('file_version.txt') else None,
)

# SUPPRIMEZ le bloc COLLECT pour le mode onefile