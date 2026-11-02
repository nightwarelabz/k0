#!/usr/bin/env python3
"""K0 aarch64 proof: the same Krell kernel module boots on QEMU
virt (aarch64) over the ARM machine layer. The serial console is
a Unix socket: bytes written to it are UART input, which the
machine layer translates to PS/2 scancodes for the shell.
Asserts the boot sequence, the shell prompt, and an interpreted
module run."""
import socket, subprocess, time, os, pathlib

HERE = pathlib.Path(__file__).parent.parent
SOCK = "/tmp/k0arm-ser.sock"
for p in (SOCK,):
    try: os.unlink(p)
    except FileNotFoundError: pass
log = HERE / "serial-arm.log"
if log.exists(): log.unlink()

qemu = subprocess.Popen([
    "qemu-system-aarch64", "-machine", "virt", "-cpu", "max",
    "-m", "128", "-kernel", str(HERE / "k0arm.elf"),
    "-device", "loader,file=modules/hello.krel,addr=0x44000000",
    "-device", "loader,file=modules/fib.krel,addr=0x44800000",
    "-device", "loader,file=modules/mem.krel,addr=0x45000000",
    "-display", "none", "-no-reboot",
    # Blocking server (no "nowait"): QEMU holds the guest until
    # the client connects, so no boot output can be lost to the
    # connect race. With nowait the guest starts immediately and
    # early serial lines vanish before the driver connects.
    "-serial", f"unix:{SOCK},server",
], cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

buf = bytearray()
ser = None
t0 = time.time()
while time.time() - t0 < 15:
    if os.path.exists(SOCK):
        try:
            ser = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            ser.connect(SOCK)
            ser.setblocking(False)
            break
        except OSError:
            ser = None
    time.sleep(0.1)
if ser is None:
    qemu.terminate()
    raise AssertionError("serial socket never appeared")

def pump(dur):
    end = time.time() + dur
    while time.time() < end:
        try:
            data = ser.recv(65536)
            if data:
                buf.extend(data)
                end = time.time() + 0.4
        except BlockingIOError:
            time.sleep(0.05)
        except OSError:
            break

t0 = time.time(); ok = False
while time.time() - t0 < 30:
    pump(0.5)
    if b"scheduler running" in buf:
        ok = True
        break
print("boot to shell:", ok)
if ok:
    ser.sendall(b"mem\n")
    pump(2.0)
    ser.sendall(b"run 1\n")
    pump(4.0)
    ser.sendall(b"ticks\n")
    pump(2.0)
try:
    qemu.terminate()
    qemu.wait(timeout=5)
except Exception:
    qemu.kill()
text = bytes(buf).decode(errors="replace")
log.write_text(text)
print(text)
assert "k0: multiboot handshake ok" in text, "handshake line missing"
assert "k0: modules in ramdisk: 3" in text, "modules not registered"
assert "k0: heap ready" in text, "heap not ready"
assert "fib(20) = 6765" in text, "interpreted module did not run"
assert "exit 0" in text, "module exit line missing"
print("ARM PROOF OK: same Krell kernel boots and runs on aarch64")
