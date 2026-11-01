#!/usr/bin/env python3
"""K0 storage proof: boot 1 stores a file, boot 2 reads it back.
Both boots share the same disk.img."""
import socket, subprocess, sys, time, os, pathlib

HERE = pathlib.Path(__file__).parent
SOCK = "/tmp/k0-mon.sock"

def boot(tag, commands, logname):
    try: os.unlink(SOCK)
    except FileNotFoundError: pass
    log = HERE / logname
    if log.exists(): log.unlink()
    qemu = subprocess.Popen([
        "qemu-system-x86_64", "-kernel", str(HERE / "k0.32.elf"),
        "-initrd", "modules/hello.krel,modules/fib.krel,modules/mem.krel",
        "-drive", "file=disk.img,format=raw,if=ide",
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
    KEYMAP = {" ": "spc", "\n": "ret", ".": "dot", "-": "minus", "_": "shift-minus"}
    def typ(text, per=0.16, settle=1.6):
        for ch in text:
            cmd(f"sendkey {KEYMAP.get(ch, ch)}", per)
        time.sleep(settle)
    t0 = time.time(); ok = False
    while time.time() - t0 < 25:
        if log.exists() and b"scheduler running" in log.read_bytes():
            ok = True; break
        time.sleep(0.2)
    print(f"[{tag}] boot to shell:", ok)
    if ok:
        for c in commands:
            typ(c)
        time.sleep(1.0)
    cmd("quit", 0.4)
    try: qemu.wait(timeout=5)
    except subprocess.TimeoutExpired: qemu.kill()
    text = log.read_text(errors="replace") if log.exists() else "NO SERIAL LOG"
    print(f"----- {tag} serial -----")
    print(text)
    return text

t1 = boot("boot1", [
    "dir\n",
    "cat readme.txt\n",
    "store note.txt persistence check one two three\n",
    "dir\n",
    "cat note.txt\n",
], "serial-storage1.log")
assert "k0: filesystem: k0fs, 1 files," in t1, "boot1: fs not mounted with 1 file"
assert "readme.txt 95 bytes" in t1, "boot1: readme missing from dir"
assert "files on an ATA disk" in t1, "boot1: readme content wrong"
assert "note.txt 31 bytes" in t1, "boot1: note missing from dir after store"
assert "persistence check one two three" in t1, "boot1: note content wrong"

t2 = boot("boot2", [
    "dir\n",
    "cat note.txt\n",
    "cat readme.txt\n",
], "serial-storage2.log")
assert "k0: filesystem: k0fs, 2 files," in t2, "boot2: fs should mount with 2 files"
assert "note.txt 31 bytes" in t2, "boot2: note missing"
assert "persistence check one two three" in t2, "boot2: note content did not persist"
print("STORAGE PROOF OK: file written in boot 1 read back in boot 2")
