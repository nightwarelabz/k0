#!/usr/bin/env python3
"""Build boot.img: a disk image K0 boots by itself, with no
host loader. Layout (512-byte sectors):

  LBA 0          stage 1 (the MBR, stage1.s)
  LBA 1..32      stage 2 (stage2.s)
  LBA 65..       the kernel as a flat binary (objcopy -O
                 binary of k0.elf)
  after that     the three Krell modules, sector-aligned
  LBA 8192..     a k0fs filesystem image (see mkdisk.py);
                 fs_init probes for it at this offset

Stage 2 loads the kernel and the modules, builds a
Multiboot information block from the BIOS memory calls,
and enters the kernel as a Multiboot loader would.
bootlayout.inc carries the sizes and addresses from here
to stage2.s."""
import math, pathlib, re, subprocess

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
FS_LBA = 8192
KERN_LBA = 65
MOD_ADDRS = [0x400000, 0x480000, 0x500000]
MODS = ["modules/hello.krel", "modules/fib.krel", "modules/mem.krel"]


def run(*args):
    subprocess.run(args, check=True, cwd=HERE)


def sectors(data):
    return math.ceil(len(data) / 512)


run("objcopy", "-O", "binary", str(ROOT / "k0.elf"), "kernel.bin")
kern = (HERE / "kernel.bin").read_bytes()
hdr = subprocess.run(["readelf", "-h", str(ROOT / "k0.elf")], check=True,
                     cwd=HERE, capture_output=True, text=True).stdout
entry = int(re.search(r"Entry point address:\s+(0x[0-9a-f]+)",
                      hdr).group(1), 16)

lba = KERN_LBA + sectors(kern)
modinfo = []
for path, addr in zip(MODS, MOD_ADDRS):
    data = (ROOT / path).read_bytes()
    modinfo.append((lba, sectors(data), len(data), addr))
    lba += sectors(data)
assert lba < FS_LBA, "kernel and modules overflow the boot area"

lines = [f".equ KERN_LBA, {KERN_LBA}",
         f".equ KERN_SECS, {sectors(kern)}",
         f".equ KERN_ENTRY, {entry}"]
for i, (mlba, msecs, mbytes, addr) in enumerate(modinfo):
    lines += [f".equ MOD{i}_LBA, {mlba}",
              f".equ MOD{i}_SECS, {msecs}",
              f".equ MOD{i}_BYTES, {mbytes}",
              f".equ MOD{i}_ADDR, {addr}"]
(HERE / "bootlayout.inc").write_text("\n".join(lines) + "\n")

run("as", "--32", "stage1.s", "-o", "stage1.o")
run("ld", "-m", "elf_i386", "-Ttext", "0x7C00", "--oformat",
    "binary", "stage1.o", "-o", "stage1.bin")
run("as", "--32", "-I", str(HERE), "stage2.s", "-o", "stage2.o")
run("ld", "-m", "elf_i386", "-Ttext", "0x7E00", "--oformat",
    "binary", "stage2.o", "-o", "stage2.bin")
stage1 = (HERE / "stage1.bin").read_bytes()
stage2 = (HERE / "stage2.bin").read_bytes()
assert len(stage1) <= 512, f"stage1 too big: {len(stage1)}"
assert len(stage2) <= 32 * 512, f"stage2 too big: {len(stage2)}"

run("python3", str(ROOT / "tools" / "mkdisk.py"), "fs.tmp")
fs = (HERE / "fs.tmp").read_bytes()
assert len(fs) == 8192 * 512

img = bytearray((FS_LBA + 8192) * 512)
img[0:len(stage1)] = stage1
img[510] = 0x55
img[511] = 0xAA
img[512:512 + len(stage2)] = stage2
img[KERN_LBA * 512:KERN_LBA * 512 + len(kern)] = kern
for (mlba, msecs, mbytes, addr), path in zip(modinfo, MODS):
    data = (ROOT / path).read_bytes()
    img[mlba * 512:mlba * 512 + len(data)] = data
img[FS_LBA * 512:FS_LBA * 512 + len(fs)] = fs
(ROOT / "boot.img").write_bytes(img)
print(f"boot.img: {len(img)} bytes; kernel {len(kern)} bytes "
      f"at LBA {KERN_LBA}, entry {entry:#x}; modules at LBAs "
      f"{[m[0] for m in modinfo]}; filesystem at LBA {FS_LBA}")
