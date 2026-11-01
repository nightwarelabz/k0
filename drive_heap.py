#!/usr/bin/env python3
"""Boot K0 in QEMU, type shell commands over the monitor, capture proof."""
import socket, subprocess, sys, time, os, pathlib

HERE = pathlib.Path(__file__).parent
SOCK = "/tmp/k0-mon.sock"
for p in (SOCK,):
    try: os.unlink(p)
    except FileNotFoundError: pass
log = HERE / "serial-heap.log"
if log.exists(): log.unlink()

qemu = subprocess.Popen([
    "qemu-system-x86_64", "-kernel", str(HERE / "k0.32.elf"),
    "-initrd", "modules/hello.krel,modules/fib.krel,modules/mem.krel",
    "-m", "128", "-display", "none", "-no-reboot",
    "-serial", f"file:{log}",
    "-monitor", f"unix:{SOCK},server,nowait",
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

for _ in range(100):
    if os.path.exists(SOCK): break
    time.sleep(0.1)
mon = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
mon.connect(SOCK)
mon.settimeout(0.3)
buf = b""
def drain():
    global buf
    try:
        while True:
            d = mon.recv(4096)
            if not d: break
            buf += d
    except socket.timeout:
        pass
def cmd(c, wait=0.25):
    try: drain()
    except Exception: return
    mon.sendall((c + "\n").encode())
    time.sleep(wait)
    drain()

KEYMAP = {" ": "spc", "\n": "ret"}
def typ(text, per=0.16, settle=1.4):
    for ch in text:
        cmd(f"sendkey {KEYMAP.get(ch, ch)}", per)
    time.sleep(settle)

def wait_serial(needle, timeout=25):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if log.exists() and needle.encode() in log.read_bytes():
            return True
        if qemu.poll() is not None:
            return False
        time.sleep(0.2)
    return False

ok = wait_serial("scheduler running")
print("boot to shell:", ok)
if ok:
    typ("heap\n")
    typ("htest\n")
    typ("heap\n")
    typ("mods\n")
    typ("run 0\n", settle=2.5)
    typ("run 1\n", settle=2.5)
    typ("run 2\n", settle=2.5)
    typ("help\n")
    typ("mem\n")
    typ("alloc\n")
    typ("free\n")
    typ("echo pure krell, running on metal\n", settle=1.2)
    typ("bogus\n")
    time.sleep(2.0)
    typ("ticks\n")
    typ("ps\n")
    cmd("screendump /tmp/k0-screen.ppm", 0.8)
cmd("quit", 0.4)
try: qemu.wait(timeout=5)
except subprocess.TimeoutExpired: qemu.kill()
print(log.read_text(errors="replace") if log.exists() else "NO SERIAL LOG")
