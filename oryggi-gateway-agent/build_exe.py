"""
Build Script for OryggiAI Gateway Agent

Creates a standalone Windows executable that:
- Requires no Python installation
- Includes all dependencies
- Works with Windows Authentication by default
- Can run as GUI or Windows Service

Usage:
    python build_exe.py

Output:
    dist/OryggiAI-Gateway.exe
"""

import os
import sys
import shutil
from pathlib import Path

def build():
    """Build the standalone executable"""
    print("=" * 60)
    print("OryggiAI Gateway Agent - Build Script")
    print("=" * 60)

    # Check PyInstaller is installed
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("Error: PyInstaller not installed!")
        print("Install with: pip install pyinstaller")
        return False

    # Get paths
    project_dir = Path(__file__).parent
    dist_dir = project_dir / "dist"
    build_dir = project_dir / "build"

    # Clean previous builds
    print("\nCleaning previous builds...")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # PyInstaller command
    print("\nBuilding executable...")

    # Create spec file content for more control
    spec_content = '''
# -*- mode: python ; coding: utf-8 -*-

import sys
sys.setrecursionlimit(5000)

block_cipher = None

a = Analysis(
    ['gateway_agent/gui_v2.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('gateway_agent/*.py', 'gateway_agent'),
    ],
    hiddenimports=[
        'win32timezone',
        'win32serviceutil',
        'win32service',
        'win32event',
        'servicemanager',
        'pyodbc',
        'websockets',
        'websockets.client',
        'asyncio',
        'tkinter',
        'tkinter.ttk',
        'tkinter.scrolledtext',
        'yaml',
        'logging.handlers',
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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='OryggiAI-Gateway',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
    version='version_info.txt' if os.path.exists('version_info.txt') else None,
)
'''

    spec_file = project_dir / "OryggiAI-Gateway.spec"
    spec_file.write_text(spec_content)
    print(f"Created spec file: {spec_file}")

    # Create version info file
    version_info = '''
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(2, 0, 0, 0),
    prodvers=(2, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [
          StringStruct(u'CompanyName', u'OryggiAI'),
          StringStruct(u'FileDescription', u'OryggiAI Gateway Agent'),
          StringStruct(u'FileVersion', u'2.0.0'),
          StringStruct(u'InternalName', u'OryggiAI-Gateway'),
          StringStruct(u'LegalCopyright', u'Copyright OryggiAI 2024'),
          StringStruct(u'OriginalFilename', u'OryggiAI-Gateway.exe'),
          StringStruct(u'ProductName', u'OryggiAI Gateway Agent'),
          StringStruct(u'ProductVersion', u'2.0.0'),
        ]
      )
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''
    version_file = project_dir / "version_info.txt"
    version_file.write_text(version_info)
    print(f"Created version info: {version_file}")

    # Run PyInstaller
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(spec_file)],
        cwd=str(project_dir),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("\nBuild failed!")
        print(result.stderr)
        return False

    # Check output
    exe_path = dist_dir / "OryggiAI-Gateway.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\nBuild successful!")
        print(f"Output: {exe_path}")
        print(f"Size: {size_mb:.1f} MB")
        return True
    else:
        print("\nBuild completed but executable not found!")
        return False


def create_icon():
    """Create a simple icon if none exists"""
    icon_path = Path(__file__).parent / "icon.ico"
    if not icon_path.exists():
        print("Note: No icon.ico found. The executable will use default icon.")
        print("To add a custom icon, place an 'icon.ico' file in the project directory.")


if __name__ == "__main__":
    create_icon()
    success = build()
    sys.exit(0 if success else 1)
