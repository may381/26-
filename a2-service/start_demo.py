# -*- coding: utf-8 -*-
"""演示环境一键自检 / 启动 / 常驻看门狗。

用法：
    python start_demo.py --check       只检查（不动任何服务）
    python start_demo.py               把没起来的服务拉起来（一次性）
    python start_demo.py --daemon      常驻看门狗：谁掉线自动重启，直到 --stop
    python start_demo.py --stop        发停止信号并关闭全部演示服务

顺序：MySQL(3308) -> P2(8080/8081) -> A2(18002) -> 演示聊天页(18080)
"""
import os
import socket
import subprocess
import sys
import time

try:
    import httpx
    _HAS_HTTPX = True
except Exception:
    _HAS_HTTPX = False

BASE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
WB = r"D:\wbtools"
MYSQLD = os.path.join(WB, "mysql-8.0.29-winx64", "bin", "mysqld.exe")
MYINI = os.path.join(WB, "my.ini")
P2_SCRIPT = os.path.join(WB, "start-p2.ps1")
SENTINEL = os.path.join(WB, "keepalive.stop")
LOGDIR = WB

DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
NO_WINDOW = 0x08000000             # CREATE_NO_WINDOW

SERVICES = [
    ("MySQL", 3308),
    ("P2 后端", 8081),
    ("A2 服务", 18002),
    ("演示聊天页", 18080),
]
PORTS_ALL = [3308, 8080, 8081, 18002, 18080]
WAITERS = {3308: 45, 8081: 240, 18002: 60, 18080: 40}


def port_open(port, timeout=0.6):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex(("127.0.0.1", int(port))) == 0


def healthy(port):
    """端口在 + (关键服务) HTTP 健康才认作活。"""
    if not port_open(port):
        return False
    if not _HAS_HTTPX:
        return True
    urls = {
        8081: "http://127.0.0.1:8081/actuator/health",
        18002: "http://127.0.0.1:18002/health",
        18080: "http://127.0.0.1:18080/api/status",
    }
    url = urls.get(port)
    if not url:
        return True
    try:
        return httpx.get(url, timeout=2).status_code == 200
    except Exception:
        return False


def wait_port(port, seconds, label):
    t0 = time.time()
    while time.time() - t0 < seconds:
        if healthy(port):
            print("   %-10s 已就绪 (%d)" % (label, port))
            return True
        time.sleep(2)
    print("   %-10s 等待超时 (%d)" % (label, port))
    return False


def spawn(args, cwd=None, log=None):
    out = open(log, "a", encoding="utf-8", errors="ignore") if log else subprocess.DEVNULL
    subprocess.Popen(
        args,
        cwd=cwd,
        stdout=out,
        stderr=subprocess.STDOUT if log else subprocess.DEVNULL,
        creationflags=DETACHED | NO_WINDOW,
        close_fds=True,
    )


def start_mysql():
    print(" > 启动 MySQL (3308)")
    spawn([MYSQLD, "--defaults-file=" + MYINI], log=os.path.join(LOGDIR, "mysql-stdout.log"))
    return wait_port(3308, WAITERS[3308], "MySQL")


def start_p2():
    print(" > 启动 P2 后端 (8080/8081)，首次需 Maven 编译，约 1-3 分钟")
    spawn(
        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-NoProfile", "-File", P2_SCRIPT],
        log=os.path.join(LOGDIR, "p2-console.log"),
    )
    return wait_port(8081, WAITERS[8081], "P2")


def start_a2():
    print(" > 启动 A2 服务 (18002)")
    spawn([PY, "main.py"], cwd=BASE, log=os.path.join(LOGDIR, "a2-run.log"))
    return wait_port(18002, WAITERS[18002], "A2")


def start_chat():
    print(" > 启动演示聊天页 (18080)")
    spawn([PY, "demo_chat_server.py"], cwd=BASE, log=os.path.join(LOGDIR, "demo-chat.log"))
    return wait_port(18080, WAITERS[18080], "聊天页")


STARTERS = {3308: start_mysql, 8081: start_p2, 18002: start_a2, 18080: start_chat}


def status():
    print("服务状态：")
    for name, port in SERVICES:
        mark = "UP" if healthy(port) else "DOWN"
        print("   %-10s %-6s %s" % (name, port, mark))


def start_once():
    print("=" * 52)
    print(" 演示环境启动")
    print("=" * 52)
    missing = [s for s in SERVICES if not healthy(s[1])]
    if not missing:
        print(" 全部服务已在运行，无需启动。")
    else:
        for name, port in missing:
            if not STARTERS[port]():
                print("\n 启动中断：%s 未能就绪，请查看 %s 下的日志。" % (name, LOGDIR))
                status()
                sys.exit(1)
        print("\n 全部服务已就绪。")
    print()
    status()
    print("\n 浏览器打开： http://127.0.0.1:18080\n")


def kill_port(port):
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             encoding="utf-8", errors="ignore").stdout
    except Exception:
        return
    pids = set()
    for line in out.splitlines():
        if (":%d" % port) in line and "LISTENING" in line:
            parts = line.split()
            pids.add(parts[-1])
    for pid in pids:
        try:
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True,
                           encoding="utf-8", errors="ignore")
        except Exception:
            pass


def daemon():
    if os.path.exists(SENTINEL):
        try:
            os.remove(SENTINEL)
        except Exception:
            pass
    log = open(os.path.join(LOGDIR, "keepalive.log"), "a", encoding="utf-8", errors="ignore")

    def logp(msg):
        line = "[%s] %s\n" % (time.strftime("%H:%M:%S"), msg)
        log.write(line)
        log.flush()
        print(line, end="")

    logp("看门狗启动，监听：%s" % ", ".join("%s:%d" % (n, p) for n, p in SERVICES))
    while True:
        if os.path.exists(SENTINEL):
            logp("收到停止信号，退出看门狗。")
            try:
                os.remove(SENTINEL)
            except Exception:
                pass
            break
        for name, port in SERVICES:
            if not healthy(port):
                logp("%s(%d) 未运行，尝试重启" % (name, port))
                STARTERS[port]()
                t0 = time.time()
                ok = False
                while time.time() - t0 < WAITERS[port]:
                    if healthy(port):
                        ok = True
                        break
                    time.sleep(2)
                logp("%s(%d) 重启 %s" % (name, port, "成功" if ok else "超时，下轮再试"))
        time.sleep(15)


def stop_all():
    # 1) 让看门狗先退出
    open(SENTINEL, "w").close()
    time.sleep(1)
    # 2) 逐个关掉监听中的端口
    for port in PORTS_ALL:
        kill_port(port)
    print(" 已发送停止信号并关闭演示相关服务。")


def main():
    if "--check" in sys.argv:
        status()
        return
    if "--stop" in sys.argv:
        stop_all()
        return
    if "--daemon" in sys.argv:
        daemon()
        return
    start_once()


if __name__ == "__main__":
    main()
