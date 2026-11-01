#!/usr/bin/env python3
"""K0 display proof: boot with the Multiboot framebuffer request,
run a shell session, screendump the result."""
import socket, subprocess, time, os, pathlib

HERE = pathlib.Path(__file__).parent
SOCK = "/tmp/k0-mon.sock"
try: os.unlink(SOCK)
except FileNotFoundError: pass
log = HERE / "serial-display.log"
if log.exists(): log.unlink()

qemu = subprocess.Popen([
    "qemu-system-x86_64", "-kernel", str(HERE / "k0.32.elf"),
    "-initrd", "modules/hello.krel,modules/fib.krel,modules/mem.krel",
    "-drive", "file=disk.img,format=raw,if=ide",
    "-vga", "std",
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
    typ("echo framebuffer console live\n")
    typ("dir\n")
    typ("run 1\n", settle=2.5)
    time.sleep(1.0)
    cmd("screendump /tmp/k0-fb.ppm", 1.0)
cmd("quit", 0.4)
try: qemu.wait(timeout=5)
except subprocess.TimeoutExpired: qemu.kill()
print(log.read_text(errors="replace") if log.exists() else "NO SERIAL LOG")
if os.path.exists("/tmp/k0-fb.ppm"):
    from PIL import Image
    im = Image.open("/tmp/k0-fb.ppm")
    im.save(HERE / "screen-fb.png")
    print("screendump:", im.size, "->", HERE / "screen-fb.png")
