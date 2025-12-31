"""
Build Script for OryggiAI Gateway Launcher

Creates a standalone launcher executable that:
- Reads configuration from gateway-launch-config.json
- Downloads and runs the main installer
- Provides GUI progress feedback
- Requests admin privileges automatically

Usage:
    python build_launcher.py

Output:
    dist/OryggiAI-Gateway-Launcher.exe
"""

import os
import sys
import shutil
from pathlib import Path


def build():
    """Build the launcher executable"""
    print("=" * 60)
    print("OryggiAI Gateway Launcher - Build Script")
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

    # Clean previous launcher builds
    print("\nCleaning previous launcher builds...")
    for f in dist_dir.glob("OryggiAI-Gateway-Launcher*"):
        if f.is_file():
            f.unlink()

    # PyInstaller spec file
    spec_content = '''
# -*- mode: python ; coding: utf-8 -*-

import sys
sys.setrecursionlimit(5000)

block_cipher = None

a = Analysis(
    ['gateway_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'json',
        'urllib.request',
        'urllib.error',
        'threading',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'numpy',
        'pandas',
        'matplotlib',
        'scipy',
        'PIL',
        'cv2',
        'pyodbc',
        'websockets',
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
    name='OryggiAI-Gateway-Launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,  # Request admin rights
    uac_uiaccess=False,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)
'''

    spec_file = project_dir / "OryggiAI-Gateway-Launcher.spec"
    spec_file.write_text(spec_content)
    print(f"Created spec file: {spec_file}")

    # Run PyInstaller
    print("\nBuilding launcher executable...")
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(spec_file)],
        cwd=str(project_dir),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("\nBuild failed!")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return False

    # Check output
    exe_path = dist_dir / "OryggiAI-Gateway-Launcher.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n{'=' * 60}")
        print("BUILD SUCCESSFUL!")
        print(f"{'=' * 60}")
        print(f"Output: {exe_path}")
        print(f"Size: {size_mb:.1f} MB")
        print(f"\nUsage:")
        print(f"  1. Place the .exe with a gateway-launch-config.json file")
        print(f"  2. Double-click to launch")
        print(f"  3. Installer will download and run automatically")

        # Create example config
        example_config = '''{
    "gateway_token": "gw_YOUR_TOKEN_HERE",
    "database_name": "YourDatabase",
    "gateway_url": "wss://api.oryggi.ai/api/gateway/ws",
    "db_host": "localhost",
    "db_port": 1433,
    "server_url": "https://api.oryggi.ai"
}'''
        config_example_path = dist_dir / "gateway-launch-config.json.example"
        config_example_path.write_text(example_config)
        print(f"\nExample config created: {config_example_path}")

        return True
    else:
        print("\nBuild completed but executable not found!")
        return False


if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
