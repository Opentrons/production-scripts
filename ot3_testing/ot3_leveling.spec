# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(
    ['C:\\Users\\22192\\production-scripts\\ot3_testing\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\22192\\production-scripts\\ot3_testing\\leveling_test\\leveling_config.json', 'ot3_testing/leveling_test')],
    hiddenimports=['ot3_testing.leveling_test.config,ot3_testing.leveling_test.type,ot3_testing.leveling_test.model.base,ot3_testing.leveling_test.report.report,ot3_testing.hardware_control.hardware_control,ot3_testing.protocol.protocol_context,ot3_testing.maintenance_api.maintenance_run'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['adodbapi'],
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
    name='ot3_leveling',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\22192\\production-scripts\\shared_data\\logo.ico'],
)
