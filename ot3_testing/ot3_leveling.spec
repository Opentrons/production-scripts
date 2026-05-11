# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/Users/andy/projects/production-scripts/ot3_testing/main.py'],
    pathex=[],
    binaries=[],
    datas=[('/Users/andy/projects/production-scripts/ot3_testing/leveling_test/leveling_config.json', 'ot3_testing/leveling_test')],
    hiddenimports=['ot3_testing.leveling_test.config,ot3_testing.leveling_test.type,ot3_testing.leveling_test.model.base,ot3_testing.leveling_test.report.report,ot3_testing.hardware_control.hardware_control,ot3_testing.protocol.protocol_context,ot3_testing.maintenance_api.maintenance_run'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pywin32,winsound,adodbapi,pyserial,playsound,crcmod'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ot3_leveling',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name='ot3_leveling.app',
    icon=None,
    bundle_identifier=None,
)
