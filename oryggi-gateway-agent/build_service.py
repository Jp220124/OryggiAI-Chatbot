"""
Build Script for OryggiAI Gateway Agent - Windows Service Edition

Creates a standalone Windows Service executable that:
- Runs as a Windows Service (background, silent)
- Starts automatically with Windows
- Auto-restarts on failure
- Logs to files instead of console
- Can be installed/removed via command line

Usage:
    python build_service.py

Output:
    dist/OryggiGatewayService.exe

Service Commands (after build):
    OryggiGatewayService.exe install    # Install as Windows Service
    OryggiGatewayService.exe start      # Start the service
    OryggiGatewayService.exe stop       # Stop the service
    OryggiGatewayService.exe remove     # Uninstall the service
    OryggiGatewayService.exe debug      # Run in debug mode (console)
"""

import os
import sys
import shutil
from pathlib import Path


def build():
    """Build the Windows Service executable"""
    print("=" * 60)
    print("OryggiAI Gateway Agent - Windows Service Build")
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
    for f in dist_dir.glob("OryggiGatewayService*"):
        if f.is_file():
            f.unlink()
        elif f.is_dir():
            shutil.rmtree(f)

    # PyInstaller spec file for Windows Service
    spec_content = '''
# -*- mode: python ; coding: utf-8 -*-

import sys
sys.setrecursionlimit(5000)

block_cipher = None

a = Analysis(
    ['gateway_agent/service.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # Windows Service requirements
        'win32timezone',
        'win32serviceutil',
        'win32service',
        'win32event',
        'servicemanager',
        'win32api',
        'pywintypes',
        # Database
        'pyodbc',
        # WebSocket
        'websockets',
        'websockets.client',
        'websockets.exceptions',
        # Async
        'asyncio',
        'asyncio.windows_events',
        # Config
        'yaml',
        'json',
        # Logging
        'logging',
        'logging.handlers',
        # Gateway agent modules
        'gateway_agent',
        'gateway_agent.config',
        'gateway_agent.database',
        'gateway_agent.connection',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',  # No GUI needed for service
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
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
    name='OryggiGatewayService',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir='.',  # Required for Windows Services
    console=True,  # Services need console for SCM communication
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
    version='version_service.txt' if os.path.exists('version_service.txt') else None,
)
'''

    spec_file = project_dir / "OryggiGatewayService.spec"
    spec_file.write_text(spec_content)
    print(f"Created spec file: {spec_file}")

    # Create version info file
    version_info = '''
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(2, 1, 0, 0),
    prodvers=(2, 1, 0, 0),
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
          StringStruct(u'FileDescription', u'OryggiAI Gateway Agent - Windows Service'),
          StringStruct(u'FileVersion', u'2.1.0'),
          StringStruct(u'InternalName', u'OryggiGatewayService'),
          StringStruct(u'LegalCopyright', u'Copyright OryggiAI 2024-2025'),
          StringStruct(u'OriginalFilename', u'OryggiGatewayService.exe'),
          StringStruct(u'ProductName', u'OryggiAI Gateway Agent Service'),
          StringStruct(u'ProductVersion', u'2.1.0'),
        ]
      )
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''
    version_file = project_dir / "version_service.txt"
    version_file.write_text(version_info)
    print(f"Created version info: {version_file}")

    # Run PyInstaller
    print("\nBuilding Windows Service executable...")
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
    exe_path = dist_dir / "OryggiGatewayService.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n{'=' * 60}")
        print("BUILD SUCCESSFUL!")
        print(f"{'=' * 60}")
        print(f"Output: {exe_path}")
        print(f"Size: {size_mb:.1f} MB")
        print(f"\nService Commands:")
        print(f"  {exe_path.name} install   - Install as Windows Service")
        print(f"  {exe_path.name} start     - Start the service")
        print(f"  {exe_path.name} stop      - Stop the service")
        print(f"  {exe_path.name} remove    - Uninstall the service")
        print(f"  {exe_path.name} debug     - Run in debug mode (console)")
        return True
    else:
        print("\nBuild completed but executable not found!")
        print("Check PyInstaller output above for errors.")
        return False


if __name__ == "__main__":
    success = build()
    sys.exit(0 if success else 1)
