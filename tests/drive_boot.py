#!/usr/bin/env python3
"""K0 bootable-image proof: boot.img is booted by the BIOS
(SeaBIOS) with no -kernel and no -initrd. Stage 1 loads
stage 2, stage 2 loads the kernel and the modules and hands
over a Multiboot information block. Boot 1 runs a module,
lists the filesystem (which lives at LBA 8192 of this
image) and stores a file. Boot 2 reads the file back."""
import socket, subprocess, time, os, pathlib

HERE = pathlib.Path(__file__).parent.parent
SOCK = "/tmp/k0-mon.sock"
KEYMAP = {" ": "spc", "\n": "ret", ".": "dot", "-": "minus"}


def boot(logname):
    try: os.unlink(SOCK)
    except FileNotFoundError: pass
    log = HERE / logname
    if log.exists(): log.unlink()
    qemu = subprocess.Popen([
        "qemu-system-x86_64",
        "-drive", "file=boot.img,format=raw,if=ide",
        "-boot", "c",
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
    def typ(text, per=0.16, settle=1.6):
        for ch in text:
            cmd(f"sendkey {KEYMAP.get(ch, ch)}", per)
        time.sleep(settle)
    t0 = time.time(); ok = False
    while time.time() - t0 < 30:
        if log.exists() and b"scheduler running" in log.read_bytes():
            ok = True; break
        time.sleep(0.2)
    print(f"{logname}: boot to shell:", ok)
    return qemu, cmd, typ, ok, log


def stop(qemu, cmd):
    cmd("quit", 0.4)
    try: qemu.wait(timeout=5)
    except subprocess.TimeoutExpired: qemu.kill()


qemu, cmd, typ, ok, log = boot("serial-boot1.log")
assert ok, "boot 1 did not reach the shell"
typ("run 1\n", settle=3.0)
typ("dir\n", settle=2.0)
typ("store proof.txt booted from disk\n", settle=2.5)
stop(qemu, cmd)
text1 = log.read_text(errors="replace")
print(text1)
assert "k0: multiboot handshake ok" in text1, "stage 2 handover failed"
assert "k0: modules in ramdisk: 3" in text1, "modules not registered"
assert "fib(20) = 6765" in text1, "module did not run"
assert "k0: filesystem: k0fs, 1 files" in text1, "fs at LBA 8192 not found"
assert "readme.txt 95 bytes" in text1, "dir listing wrong"

qemu, cmd, typ, ok, log = boot("serial-boot2.log")
assert ok, "boot 2 did not reach the shell"
typ("cat proof.txt\n", settle=2.5)
stop(qemu, cmd)
text2 = log.read_text(errors="replace")
print(text2)
assert "k0: filesystem: k0fs, 2 files" in text2, "stored file lost"
assert "booted from disk" in text2, "stored file contents wrong"
print("BOOT PROOF OK: BIOS boot from boot.img, modules loaded by "
      "stage 2, filesystem persisted across boots")
