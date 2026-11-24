"""Launch Streamlit inside a native desktop window (pywebview).

Supports development (`python desktop_app.py`) and frozen PyInstaller builds.
When frozen, a second process of the same .exe runs the Streamlit server.
Falls back to the default browser if the native window cannot open.
"""

from __future__ import annotations

import atexit
import os
import socket
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from app_paths import app_dir, bundle_dir, is_frozen

HOST = "127.0.0.1"
PORT = 8501
URL = f"http://{HOST}:{PORT}"
READY_TIMEOUT_SEC = 90
STREAMLIT_FLAG = "--run-streamlit-server"


def log_path() -> Path:
    return app_dir() / "desktop_app.log"


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n"
    try:
        with log_path().open("a", encoding="utf-8") as file:
            file.write(line)
    except OSError:
        pass


def show_message(title: str, text: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10 if "Error" in title or "Hata" in title else 0x40)
    except Exception:
        print(f"{title}: {text}")


def streamlit_script() -> Path:
    return bundle_dir() / "streamlit_app.py"


def port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def wait_until_ready(url: str, timeout: float = READY_TIMEOUT_SEC) -> None:
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if 200 <= response.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = str(exc)
        time.sleep(0.4)
    raise RuntimeError(f"Streamlit did not become ready at {url}. Last error: {last_error}")


def run_streamlit_server() -> None:
    """Entry used by the child process (dev or frozen)."""
    script = streamlit_script()
    if not script.exists():
        raise SystemExit(f"Missing Streamlit app: {script}")

    os.chdir(app_dir())
    sys.path.insert(0, str(bundle_dir()))
    log(f"streamlit-server start script={script}")

    from streamlit.web import bootstrap

    flag_options = {
        "server_headless": True,
        "server_address": HOST,
        "server_port": PORT,
        "browser_gatherUsageStats": False,
        "global_developmentMode": False,
    }
    bootstrap.run(str(script), False, [], flag_options)


def start_streamlit() -> subprocess.Popen:
    cwd = str(app_dir())
    env = os.environ.copy()
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

    if is_frozen():
        command = [sys.executable, STREAMLIT_FLAG]
    else:
        command = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(streamlit_script()),
            "--server.headless=true",
            "--server.address",
            HOST,
            "--server.port",
            str(PORT),
            "--browser.gatherUsageStats=false",
            "--global.developmentMode=false",
        ]

    log(f"starting server: {' '.join(command)}")
    return subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_process(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()


def ensure_sidecar_files() -> None:
    target_dir = app_dir()
    example_src = bundle_dir() / ".env.example"
    example_dst = target_dir / ".env.example"
    if example_src.exists() and not example_dst.exists():
        example_dst.write_text(example_src.read_text(encoding="utf-8"), encoding="utf-8")


def keep_alive_while_server_up() -> None:
    while port_is_open(HOST, PORT):
        time.sleep(1)


def open_in_browser(reason: str) -> None:
    log(f"opening browser fallback: {reason}")
    webbrowser.open(URL)
    show_message(
        "Personal Finance Tracker",
        "Masaüstü penceresi açılamadı; tarayıcıda açıldı.\n"
        f"Detay: {reason}\n\nLog: {log_path()}\nURL: {URL}",
    )
    keep_alive_while_server_up()


def open_ui() -> None:
    """Prefer Edge WebView2 window; fall back to default browser.

    Frozen builds must not use the WinForms/pythonnet backend — PyInstaller
    cannot reliably resolve Python.Runtime.dll on end-user machines.
    """
    # Force Edge Chromium before importing platform backends.
    os.environ.setdefault("PYWEBVIEW_GUI", "edgechromium")

    try:
        import webview
    except ImportError as exc:
        open_in_browser(f"webview missing: {exc}")
        return

    try:
        window = webview.create_window(
            title="Personal Finance Tracker",
            url=URL,
            width=1280,
            height=840,
            min_size=(900, 600),
        )
        log("webview window created, starting UI loop (edgechromium)")
        # Explicit GUI avoids winforms -> pythonnet -> Python.Runtime.dll crash.
        webview.start(gui="edgechromium")
        log("webview loop ended")
        _ = window
    except Exception as exc:
        log(f"webview failed: {exc}\n{traceback.format_exc()}")
        open_in_browser(str(exc))


def main() -> None:
    if STREAMLIT_FLAG in sys.argv:
        try:
            run_streamlit_server()
        except Exception:
            log(f"streamlit-server crashed:\n{traceback.format_exc()}")
            raise
        return

    try:
        log(f"launcher start frozen={is_frozen()} app_dir={app_dir()} bundle={bundle_dir()}")
        ensure_sidecar_files()
        script = streamlit_script()
        if not script.exists():
            show_message("Hata", f"Streamlit dosyası yok:\n{script}")
            raise SystemExit(f"Missing Streamlit app: {script}")

        if port_is_open(HOST, PORT):
            log("port already open, reusing server")
            proc = None
        else:
            proc = start_streamlit()
            atexit.register(stop_process, proc)
            try:
                wait_until_ready(URL)
                log("server ready")
            except Exception as exc:
                stop_process(proc)
                log(f"server failed: {exc}")
                show_message(
                    "Hata",
                    "Uygulama sunucusu başlamadı.\n"
                    f"{exc}\n\nLog: {log_path()}",
                )
                raise

        open_ui()
        stop_process(proc)
    except SystemExit:
        raise
    except Exception as exc:
        log(f"fatal:\n{traceback.format_exc()}")
        show_message("Hata", f"{exc}\n\nLog: {log_path()}")
        raise


if __name__ == "__main__":
    main()
