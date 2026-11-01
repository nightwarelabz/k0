import socket, subprocess, time, os, pathlib
HERE = pathlib.Path(__file__).parent
SOCK = "/tmp/k0-mon2.sock"
try: os.unlink(SOCK)
except FileNotFoundError: pass
log = HERE / "serial-verify.log"
if log.exists(): log.unlink()
qemu = subprocess.Popen(["qemu-system-x86_64", "-kernel", str(HERE / "k0.32.elf"),
    "-m", "128", "-display", "none", "-no-reboot",
    "-serial", f"file:{log}", "-monitor", f"unix:{SOCK},server,nowait"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(100):
    if os.path.exists(SOCK): break
    time.sleep(0.1)
mon = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); mon.connect(SOCK)
time.sleep(4.0)
mon.sendall(b"screendump /tmp/k0-verify.ppm\n"); time.sleep(0.8)
mon.sendall(b"quit\n"); time.sleep(0.4)
try: qemu.wait(timeout=5)
except subprocess.TimeoutExpired: qemu.kill()
print(log.read_text(errors="replace"))
