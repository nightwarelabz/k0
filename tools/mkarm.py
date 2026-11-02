#!/usr/bin/env python3
"""Generate the aarch64 machine layer's build-time includes.

boot_arm.inc: the byte length of each ramdisk module, which the
fabricated Multiboot module entries carry.
scmap.inc / scshift.inc: for each ASCII code, the PS/2 set-1
scancode that produces it and whether shift is required. The
tables are the inverse of the kernel's own scancode tables
(TAB_PLAIN / TAB_SHIFT in gen_kernel.py), plus the two keys the
shell handles as raw scancodes: Enter (28) for LF/CR and
Backspace (14) for BS/DEL."""
import ast, pathlib, re

HERE = pathlib.Path(__file__).parent

ROOT = HERE.parent
OUT = ROOT / "arch" / "aarch64"
src = (ROOT / "kernel" / "gen_kernel.py").read_text()
tables = {}
for name in ("TAB_PLAIN", "TAB_SHIFT"):
    m = re.search(name + r"\s*=\s*(\[[^\]]*\])", src)
    tables[name] = ast.literal_eval(m.group(1))
plain, shift = tables["TAB_PLAIN"], tables["TAB_SHIFT"]
assert len(plain) == 58 and len(shift) == 58

scmap = [0] * 128
scshift = [0] * 128
for sc in range(58):
    for table, flag in ((plain, 0), (shift, 1)):
        c = table[sc]
        if c and scmap[c] == 0:
            scmap[c] = sc
            scshift[c] = flag
for c in (10, 13):
    scmap[c] = 28
for c in (8, 127):
    scmap[c] = 14
scmap[27] = 1

def emit(name, values):
    lines = []
    for i in range(0, 128, 16):
        lines.append("    .byte " + ",".join(str(v) for v in values[i:i+16]))
    (OUT / name).write_text("\n".join(lines) + "\n")

emit("scmap.inc", scmap)
emit("scshift.inc", scshift)

mods = ["modules/hello.krel", "modules/fib.krel", "modules/mem.krel"]
with open(OUT / "boot_arm.inc", "w") as f:
    for i, path in enumerate(mods):
        size = (ROOT / path).stat().st_size
        f.write(f"    .equ ARM_MOD{i}_LEN, {size}\n")
print("mkarm: includes generated")
