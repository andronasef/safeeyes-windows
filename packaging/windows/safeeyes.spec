# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the bundled Windows build of Safe Eyes.

Build from the project root:
    .venv\\Scripts\\pyinstaller.exe packaging\\windows\\safeeyes.spec

Produces dist/SafeEyes/SafeEyes.exe (onedir). The plugins are loaded
dynamically by string at runtime, so the plugin tree is shipped as on-disk data
(found via safeeyes.utility.SYSTEM_PLUGINS_DIR) and modules they import but that
are not statically reachable are listed as hidden imports.
"""

import os

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
SAFEEYES = os.path.join(ROOT, "safeeyes")

# Data bundled under _internal/safeeyes/... so that
# safeeyes.utility.BIN_DIRECTORY (dirname of utility.py) finds it at runtime.
datas = [
    (os.path.join(SAFEEYES, "config"), "safeeyes/config"),
    (os.path.join(SAFEEYES, "plugins"), "safeeyes/plugins"),
    (os.path.join(SAFEEYES, "platform"), "safeeyes/platform"),
    (os.path.join(SAFEEYES, "resource"), "safeeyes/resource"),
]

# Imports reachable ONLY through dynamically-loaded plugins, which PyInstaller's
# static analysis cannot see:
#   - QtMultimedia: audiblealert (QSoundEffect)
#   - platform_api.{lock,fullscreen,media}: screensaver/donotdisturb/mediacontrol
hiddenimports = [
    "PySide6.QtMultimedia",
    "PySide6.QtNetwork",
    "safeeyes.platform_api.lock",
    "safeeyes.platform_api.fullscreen",
    "safeeyes.platform_api.media",
    "safeeyes.platform_api.keyboard_block",
    "safeeyes.platform_api.suspend",
]

# Trim the bundle: Safe Eyes only needs Core/Gui/Widgets/Multimedia/Network.
excludes = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQml",
    "PySide6.QtQmlModels",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtBluetooth",
    "PySide6.QtPositioning",
    "PySide6.QtNfc",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "tkinter",
    "unittest",
    "pydoc",
]

a = Analysis(
    [os.path.join(SAFEEYES, "__main__.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# Module-level `excludes` drop Python bindings but NOT the Qt6*.dll binaries or
# the qml/ plugin data the PySide6 hook collects. Strip those by name so the
# bundle only ships what Safe Eyes actually loads (Core/Gui/Widgets/Multimedia/
# Network and their dependencies).
_DROP_TOKENS = (
    "Qt6Qml",
    "Qt6Quick",
    "Qt63D",
    "Qt6Charts",
    "Qt6DataVisualization",
    "Qt6Designer",
    "Qt6WebEngine",
    "Qt6WebChannel",
    "Qt6WebSockets",
    "Qt6Pdf",
    "Qt6Bluetooth",
    "Qt6Nfc",
    "Qt6Sensors",
    "Qt6SerialPort",
    "/qml/",
    "\\qml\\",
    "QtQml",
    "QtQuick",
    "Qt3D",
    "QtCharts",
    "QtDataVisualization",
    "QtPdf",
)


def _keep(entry):
    name = entry[0].replace("\\", "/")
    return not any(tok.replace("\\", "/") in name for tok in _DROP_TOKENS)


a.binaries = [e for e in a.binaries if _keep(e)]
a.datas = [e for e in a.datas if _keep(e)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SafeEyes",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.join(SPECPATH, "safeeyes.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SafeEyes",
)
