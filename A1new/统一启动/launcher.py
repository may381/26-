"""Central startup shortcuts; original project directories stay in place."""
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
SERVICES = {
    "tourism": (8091, BASE / "a1-guide", ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BASE / "a1-guide" / "start-school.ps1")]),
    "fraud": (8000, BASE / "外包A30" / "anti-fraud", ["cmd.exe", "/c", str(BASE / "外包A30" / "anti-fraud" / "start-school-backend.bat")]),
    "web": (8095, BASE / "A1new", [sys.executable, "server.py"]),
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
        print("Port checks do not verify school model inference.")
        return
    for name in SERVICES if mode == "all" else [mode]:
        start(name)
    if mode in ("all", "web"):
        for _ in range(20):
            if listening(8095):
                webbrowser.open("http://127.0.0.1:8095/")
                break
            time.sleep(0.5)
        else:
            print("Preview not ready. Check the web terminal.")

if __name__ == "__main__":
    main()
