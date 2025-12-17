# -*- mode: python -*-
# -*- coding: utf-8 -*-
import os
import sys

block_cipher = None

# Collecter tous les fichiers de données nécessaires
datas = [
    ('ui/localization/translations/*.json', 'ui/localization/translations'),
    ('ui/resources/icons/*', 'ui/resources/icons'),
    ('ui/resources/flags/*', 'ui/resources/flags'),
]

# Utiliser un chemin d'icône PNG pour Linux au lieu de ICO
icon_path = None
if os.path.exists('ui/resources/icons/logo.png'):
    icon_path = 'ui/resources/icons/logo.png'
elif os.path.exists('ui/resources/icons/logo.ico'):
    icon_path = 'ui/resources/icons/logo.ico'

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
        'utils.dataset_database',
        'utils.dataset_project_manager',
        
        # UI widgets
        'ui.widgets.tabs.project_config_widget',
        'ui.widgets.tabs.coding_panel',
        'ui.widgets.tabs.relations_graph_widget',
        'ui.widgets.tabs.relations_config',
        'ui.widgets.dialogs.code_dialogs',
        'ui.localization.translator',
        'ui.widgets.language_selector',
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

# MODE ONEFILE : Tout dans un seul exécutable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Liris',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Mettre False pour masquer la console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)