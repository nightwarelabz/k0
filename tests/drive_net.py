#!/usr/bin/env python3
"""K0 network proof: boot with an e1000 on QEMU user networking,
ping the gateway 10.0.2.2 from the shell."""
import socket, subprocess, time, os, pathlib

HERE = pathlib.Path(__file__).parent.parent
SOCK = "/tmp/k0-mon.sock"
try: os.unlink(SOCK)
except FileNotFoundError: pass
log = HERE / "serial-net.log"
if log.exists(): log.unlink()

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
    typ("ping\n", settle=4.0)
    typ("ping\n", settle=4.0)
cmd("quit", 0.4)
try: qemu.wait(timeout=5)
except subprocess.TimeoutExpired: qemu.kill()
text = log.read_text(errors="replace") if log.exists() else "NO SERIAL LOG"
print(text)
assert "k0: network: e1000 mac " in text, "e1000 not detected"
assert "reply from 10.0.2.2: icmp_seq=1" in text, "no ICMP echo reply from the gateway"
print("NETWORK PROOF OK: ARP + ICMP echo against 10.0.2.2 from the K0 shell")
