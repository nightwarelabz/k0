#!/usr/bin/env python3
"""K0 TCP proof: a server on the host (this machine) listens on
port 7777. The K0 shell command `tcp 7777 hello over tcp`
connects to it through QEMU user networking (the gateway
10.0.2.2 is the host), sends the text, and prints the reply.
The server answers "reply:<text>" and closes."""
import socket, subprocess, threading, time, os, pathlib

HERE = pathlib.Path(__file__).parent.parent
SOCK = "/tmp/k0-mon.sock"
try: os.unlink(SOCK)
except FileNotFoundError: pass
log = HERE / "serial-tcp.log"
if log.exists(): log.unlink()

received = []

def server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 7777))
    s.listen(1)
    s.settimeout(60)
    try:
        conn, _ = s.accept()
        conn.settimeout(10)
        data = conn.recv(4096)
        received.append(data)
        conn.sendall(b"reply:" + data + b"\n")
        conn.close()
    except Exception as e:
        received.append(b"SERVER-ERROR " + str(e).encode())
    s.close()

threading.Thread(target=server, daemon=True).start()
time.sleep(0.3)

qemu = subprocess.Popen([
    "qemu-system-x86_64", "-kernel", str(HERE / "k0.32.elf"),
    "-initrd", "modules/hello.krel,modules/fib.krel,modules/mem.krel",
    "-drive", "file=disk.img,format=raw,if=ide",
    "-netdev", "user,id=n0", "-device", "e1000,netdev=n0",
    "-m", "128", "-display", "none", "-no-reboot",
    "-serial", f"file:{log}",
    "-monitor", f"unix:{SOCK},server,nowait",
], cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(100):
    if os.path.exists(SOCK): break
    time.sleep(0.1)
mon = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
mon.connect(SOCK); mon.settimeout(0.3)
def cmd(c, wait=0.25):
    try: mon.recv(4096)
    except Exception: pass
    mon.sendall((c + "\n").encode()); time.sleep(wait)
    try: mon.recv(4096)
    except Exception: pass
KEYMAP = {" ": "spc", "\n": "ret", ".": "dot", "-": "minus"}
def typ(text, per=0.16, settle=1.6):
    for ch in text:
        cmd(f"sendkey {KEYMAP.get(ch, ch)}", per)
    time.sleep(settle)

t0 = time.time(); ok = False
while time.time() - t0 < 25:
    if log.exists() and b"scheduler running" in log.read_bytes():
        ok = True; break
    time.sleep(0.2)
print("boot to shell:", ok)
if ok:
    typ("tcp 7777 hello over tcp\n", settle=8.0)
cmd("quit", 0.4)
try: qemu.wait(timeout=5)
except subprocess.TimeoutExpired: qemu.kill()
text = log.read_text(errors="replace") if log.exists() else "NO SERIAL LOG"
print(text)
print("server received:", received)
assert received and received[0] == b"hello over tcp", "server did not get the payload"
assert "reply:hello over tcp" in text, "kernel did not print the reply"
assert "tcp: closed" in text, "connection did not close cleanly"
print("TCP PROOF OK: connect, send, reply, close against 10.0.2.2:7777")
