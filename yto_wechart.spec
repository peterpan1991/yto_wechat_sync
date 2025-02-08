# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\Administrator\\Documents\\GitHub\\yto_wechat_sync\\.\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\Administrator\\Documents\\GitHub\\yto_wechat_sync\\config.py', '.'), ('C:\\Users\\Administrator\\Documents\\GitHub\\yto_wechat_sync\\logger.py', '.'), ('C:\\Users\\Administrator\\Documents\\GitHub\\yto_wechat_sync\\services', 'services'), ('C:\\Users\\Administrator\\Documents\\GitHub\\yto_wechat_sync\\models', 'models'), ('C:\\Users\\Administrator\\Documents\\GitHub\\yto_wechat_sync\\handlers', 'handlers'), ('C:\\Users\\Administrator\\Documents\\GitHub\\yto_wechat_sync\\logs', 'logs')],
    hiddenimports=['redis', 'uiautomation', 'selenium', 'selenium.webdriver.common.by', 'selenium.webdriver.support.ui', 'selenium.webdriver.support.expected_conditions', 'selenium.webdriver.chrome.options', 'selenium.webdriver.common.keys'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='yto_wechart',
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
)
