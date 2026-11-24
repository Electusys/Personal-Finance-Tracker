# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Personal Finance Tracker desktop app."""

from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None


def without_tests(datas, binaries, hidden):
    """Drop *tests* packages that collect_all pulls in and bloats the build."""
    datas = [item for item in datas if "tests" not in str(item[0]).replace("\\", "/").lower()]
    binaries = [item for item in binaries if "tests" not in str(item[0]).replace("\\", "/").lower()]
    hidden = [
        name
        for name in hidden
        if ".tests" not in name and not name.endswith(".tests") and ".testing" not in name
    ]
    return datas, binaries, hidden


streamlit_datas, streamlit_binaries, streamlit_hidden = without_tests(*collect_all("streamlit"))
altair_datas, altair_binaries, altair_hidden = without_tests(*collect_all("altair"))

# Prefer lean pandas collection — avoid shipping pandas.tests
pandas_datas = collect_data_files("pandas", includes=["**/*.dll", "**/*.so", "**/*.pyd", "**/_libs/**"])
try:
    import pandas._libs  # noqa: F401
except Exception:
    pass

datas = [
    ("streamlit_app.py", "."),
    ("ai_assistant.py", "."),
    ("personel_finance_tracker.py", "."),
    ("app_paths.py", "."),
    (".env.example", "."),
]
datas += streamlit_datas + altair_datas + pandas_datas
datas += collect_data_files("streamlit")

binaries = streamlit_binaries + altair_binaries

hiddenimports = list(
    set(
        streamlit_hidden
        + altair_hidden
        + [
            "streamlit",
            "streamlit.web",
            "streamlit.web.bootstrap",
            "streamlit.runtime",
            "streamlit.runtime.scriptrunner",
            "streamlit.runtime.scriptrunner.magic_funcs",
            "pandas",
            "pandas._libs",
            "pandas._libs.tslibs.timedeltas",
            "pandas._libs.tslibs.np_datetime",
            "pandas._libs.tslibs.nattype",
            "pandas._libs.tslibs.timestamps",
            "pandas._libs.skiplist",
            "pyarrow",
            "dotenv",
            "webview",
            "google",
            "google.genai",
            "google.genai.types",
            "google.genai.client",
            "ai_assistant",
            "personel_finance_tracker",
            "app_paths",
            "streamlit_app",
        ]
    )
)

# Explicitly exclude test suites from analysis noise and binary size
excludes = [
    "pandas.tests",
    "numpy.tests",
    "google.genai.tests",
    "streamlit.testing",
    "pytest",
    "unittest",
]

a = Analysis(
    ["desktop_app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PersonalFinanceTracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PersonalFinanceTracker",
)
