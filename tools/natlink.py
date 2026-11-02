#!/usr/bin/env python3
"""Build a native module for K0: modules/<name>.krell ->
modules/<name>.nat.

The module source is compiled by the Krell x86_64 backend,
assembled, and linked at the native region base
(0x2000000) with nat.ld. The six host services are bound to
the kernel's nk* implementations: their addresses are read
from k0.elf with nm, so the kernel must be built first.
The output is the 16-byte K0N1 header (magic, entry offset,
file size, memory size including the bss span) followed by
the flat image."""
import os, pathlib, re, struct, subprocess, sys

HERE = pathlib.Path(__file__).parent
KRELLC = pathlib.Path(os.environ.get("KRELLC", pathlib.Path.home() / "workspace" / "rung" / "krellc"))
NAT_BASE = 0x2000000
SERVICES = {"kprint": "nkprint", "kputn": "nkputn",
            "kputc": "nkputc", "kticks": "nkticks",
            "kalloc": "nkalloc", "kfree": "nkfree"}
BUILD = HERE.parent / "natbuild"


def run(*args, env=None):
    subprocess.run(args, check=True, cwd=HERE, env=env)


def symbols(elf):
    out = subprocess.run(["nm", str(elf)], check=True, cwd=HERE,
                         capture_output=True, text=True).stdout
    syms = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3:
            syms[parts[2]] = int(parts[0], 16)
    return syms


def main():
    src = str(pathlib.Path(sys.argv[1]).absolute())
    out = str(pathlib.Path(sys.argv[2]).absolute())
    stem = pathlib.Path(src).stem
    BUILD.mkdir(exist_ok=True)
    krel = BUILD / f"{stem}.krel"
    asm = BUILD / f"{stem}.s"
    obj = BUILD / f"{stem}.o"
    elf = BUILD / f"{stem}.elf"
    img = BUILD / f"{stem}.bin"
    env = dict(os.environ,
               KRELL_TARGETS=str(KRELLC.parent / "targets"))
    run(str(KRELLC), "parse", src, "-o", str(krel), env=env)
    run(str(KRELLC), "build", str(krel), "--target", "x86_64",
        "-o", str(asm), env=env)
    run("cc", "-c", str(asm), "-o", str(obj))
    ksyms = symbols(HERE.parent / "k0.elf")
    defsyms = []
    for call, kern in SERVICES.items():
        assert kern in ksyms, f"kernel symbol {kern} missing"
        defsyms.append(f"--defsym={call}={ksyms[kern]}")
    run("ld", "-T", str(HERE.parent / "arch" / "x86_64" / "nat.ld"), *defsyms, str(obj), "-o", str(elf))
    msyms = symbols(elf)
    entry_off = msyms["main"] - NAT_BASE
    mem_end = msyms["_mem_end"]
    run("objcopy", "-O", "binary", str(elf), str(img))
    data = img.read_bytes()
    header = b"K0N1" + struct.pack("<III", entry_off, len(data),
                                   mem_end - NAT_BASE)
    pathlib.Path(out).write_bytes(header + data)
    print(f"{out}: entry +{entry_off}, image {len(data)} bytes, "
          f"memory {mem_end - NAT_BASE} bytes")


if __name__ == "__main__":
    main()
