import PyInstaller.__main__
import sys
import PyInstaller.compat

# Corriger le chemin Python que PyInstaller utilise
PyInstaller.compat.python_executable = sys.executable

PyInstaller.__main__.run([
    'main.py',
    '--onefile',
    '--windowed',
    '--name=Liris',
    '--icon=ui/resources/icons/logo.ico',
    '--add-data=ui/resources;ui/resources',
    '--hidden-import=PyQt5',
    '--hidden-import=pydgraph',
])