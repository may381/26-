"""Start and inspect the A1, tourism, fraud, and preview services."""
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
SERVICES = {
    "a1": (int(os.environ.get("A1_PORT", "8093")), BASE / "a1-orchestrator", ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BASE / "a1-orchestrator" / "启动A1联调服务.ps1")]),
    "tourism": (int(os.environ.get("PORT", "8091")), BASE / "a1-guide", ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BASE / "a1-guide" / "start-source.ps1")]),
    "fraud": (int(os.environ.get("FRAUD_PORT", "8000")), BASE / "anti-fraud", ["cmd.exe", "/c", str(BASE / "anti-fraud" / "start-backend.bat")]),
    "web": (int(os.environ.get("A1_WEB_PORT", "8095")), BASE / "A1new", [sys.executable, "server.py"]),
}

def listening(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False

def start(name):
    port, directory, command = SERVICES[name]
    if listening(port):
        print(f"{name}: port {port} already running; skipped.")
        return
    if not directory.is_dir():
        raise RuntimeError(f"Project directory missing: {directory}")
    # Visible consoles are intentional so the user can inspect startup errors.
    subprocess.Popen(command, cwd=directory, creationflags=subprocess.CREATE_NEW_CONSOLE)
    print(f"{name}: launch requested, port {port}. Check its terminal for errors.")

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "status":
        for name, (port, _, _) in SERVICES.items():
            print(f"{name} ({port}): {'RUNNING' if listening(port) else 'STOPPED'}")
        print("Port checks do not verify authentication, school model inference, or business results.")
        return
    for name in SERVICES if mode == "all" else [mode]:
        start(name)
    if mode in ("all", "web"):
        for _ in range(20):
            web_port=SERVICES["web"][0]
            if listening(web_port):
                webbrowser.open(f"http://127.0.0.1:{web_port}/")
                break
            time.sleep(0.5)
        else:
            print("Preview not ready. Check the web terminal.")

if __name__ == "__main__":
    main()
