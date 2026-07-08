# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for BambuDashboard — single-file .exe for Windows.
#
# Build command (from project root):
#   .\build.ps1
# or manually:
#   pyinstaller bambu_dashboard.spec --clean --noconfirm
#
# Output: dist\BambuDashboard.exe

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('logo2.ico', '.'),
        ('translations.py', '.'),
        ('app_icon.py', '.'),
        ('gui/icon_helper.py', 'gui'),
    ],
    hiddenimports=[
        'PySide6.QtNetwork',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebChannel',
        'PySide6.QtPositioning',
        'paho.mqtt.client',
        'paho.mqtt.enums',
        'paho.mqtt.reasoncodes',
        'paho.mqtt.properties',
        'ssl',
        'certifi',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas',
        'PIL', 'cv2', 'PyQt5', 'PyQt6', 'wx',
        'IPython', 'notebook', 'jupyter', 'test', 'unittest',
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
    name='BambuDashboard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo2.ico',       # relative path — works on any machine
)
