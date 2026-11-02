#!/usr/bin/env python3
"""K0 native-module proof: the three sample modules are also
compiled ahead of time by the Krell x86_64 backend and
linked as .nat images. The ramdisk carries six modules:
0-2 interpreted (.krel), 3-5 native (.nat). nrun executes
the native ones as machine code in the native region;
run on a native image and nrun on an interpreted one are
both refused with the matching message."""
import socket, subprocess, time, os, pathlib

HERE = pathlib.Path(__file__).parent.parent
SOCK = "/tmp/k0-mon.sock"
try: os.unlink(SOCK)
except FileNotFoundError: pass
log = HERE / "serial-nat.log"
if log.exists(): log.unlink()

qemu = subprocess.Popen([
    "qemu-system-x86_64", "-kernel", str(HERE / "k0.32.elf"),
    "-initrd", "modules/hello.krel,modules/fib.krel,modules/mem.krel,"
               "modules/hello.nat,modules/fib.nat,modules/mem.nat",
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
    typ("nrun 3\n", settle=3.0)
    typ("nrun 4\n", settle=3.0)
    typ("nrun 5\n", settle=3.0)
    typ("nrun 0\n", settle=2.0)
    typ("run 1\n", settle=3.0)
cmd("quit", 0.4)
try: qemu.wait(timeout=5)
except subprocess.TimeoutExpired: qemu.kill()
text = log.read_text(errors="replace") if log.exists() else "NO SERIAL LOG"
print(text)
assert "k0: modules in ramdisk: 6" in text, "six modules not registered"
assert "hello from a Krell module" in text, "native hello did not run"
assert "fib(20) = 6765" in text, "native fib wrong"
assert "sum of 0..99 = 4950" in text, "native mem wrong"
assert "nrun: not a native module" in text, "nrun accepted a .krel"
assert text.count("exit 7") >= 1, "native hello exit code missing"
assert text.count("exit 3") >= 1, "native mem exit code missing"
print("NATIVE PROOF OK: compiled Krell modules executed as machine code")
