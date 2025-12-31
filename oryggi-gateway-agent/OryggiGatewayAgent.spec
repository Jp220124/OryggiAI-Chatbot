# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for OryggiAI Gateway Agent

To build:
  pip install pyinstaller
  pyinstaller OryggiGatewayAgent.spec

This creates a standalone .EXE that doesn't require Python to be installed.
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all gateway_agent submodules
hiddenimports = [
    'gateway_agent',
    'gateway_agent.main',
    'gateway_agent.gui',
    'gateway_agent.config',
    'gateway_agent.connection',
    'gateway_agent.database',
    'websockets',
    'websockets.client',
    'websockets.exceptions',
    'pyodbc',
    'yaml',
    'asyncio',
    'tkinter',
    'tkinter.ttk',
    'tkinter.scrolledtext',
    'tkinter.messagebox',
]

a = Analysis(
    ['gateway_agent/gui.py'],  # Entry point for GUI
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'tensorflow',
        'torch',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='OryggiGatewayAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window - GUI only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if available
    version='file_version_info.txt' if sys.platform == 'win32' else None,
)
