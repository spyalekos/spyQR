# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.building.api import Splash
from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = []
if os.path.exists('assets'):
    datas.append(('assets', 'assets'))

binaries = []
hiddenimports = [
    'generator',
    'history',
    'scanner',
    'version',
    'flet',
    'flet_desktop',
    'flet_desktop.version',
    'flet_audio',
    'flet_permission_handler',
    'flet_lottie',
    'flet_spinkit',
    'flet_code_editor',
    'flet_color_pickers',
    'flet_secure_storage',
    'flet_charts',
    'flet_datatable2',
    'flet_map',
    'flet_webview',
    'flet_flashlight',
    'flet_geolocator',
    'flet_camera',
    'cv2',
    'qrcode',
    'barcode',
    'barcode.writer',
    'zxingcpp',
    'PIL',
    'numpy',
    'openpyxl',
    'et_xmlfile',
    'fpdf',
    'fpdf2',
    'defusedxml',
    'fonttools',
]

packages_to_collect = [
    'flet',
    'flet_desktop',
    'flet_audio',
    'flet_permission_handler',
    'flet_lottie',
    'flet_spinkit',
    'flet_code_editor',
    'flet_color_pickers',
    'flet_secure_storage',
    'flet_charts',
    'flet_datatable2',
    'flet_map',
    'flet_webview',
    'flet_flashlight',
    'flet_geolocator',
    'flet_camera',
    'zxingcpp',
    'barcode',
    'openpyxl',
    'fpdf',
    'fpdf2',
]

for pkg in packages_to_collect:
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hiddenimports
    except Exception:
        pass

a = Analysis(
    ['src/main.py'],
    pathex=['src', '.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['flet.testing', 'tkinter', 'unittest', 'pydoc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Deduplicate binaries: remove root-level duplicate copies of DLLs already inside flet_desktop\app\flet\
flet_desktop_bins = {
    os.path.basename(dest.replace('/', '\\')).lower()
    for dest, src, *extra in a.binaries
    if 'flet_desktop\\app\\flet\\' in dest.replace('/', '\\')
}

a.binaries = [
    item for item in a.binaries
    if not ('\\' not in item[0].replace('/', '\\') and os.path.basename(item[0].replace('/', '\\')).lower() in flet_desktop_bins)
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

splash = Splash(
    'assets/spyqr_splash.jpg',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,
    text_size=12,
    minify_script=True,
    always_on_top=True,
)

icon_file = 'assets/icon.ico' if os.path.exists('assets/icon.ico') else None

exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SpyQR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)
