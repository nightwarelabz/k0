#!/usr/bin/env python3
"""Assemble kernel.krell from the two template halves.

Emits the data section: every string as an i8 blob with a
dataptr accessor fn, plus the keyboard tables and the
spinner cycle. Data indices are assigned here, so the
templates only ever call the s_* accessors.
"""
import pathlib

HERE = pathlib.Path(__file__).parent

STRINGS = [
    ("bark0", "K0"),
    ("barup", "uptime"),
    ("barunit", "s"),
    ("bartick", "ticks"),
    ("barfree", "free frames"),
    ("banner1", "K0"),
    ("banner2", "a kernel in pure Krell"),
    ("bootok", "k0: multiboot handshake ok"),
    ("bootbad", "k0: no multiboot magic; continuing anyway"),
    ("bootpfx", "k0: "),
    ("mema", "physical memory: "),
    ("memb", " KiB | frames free "),
    ("memc", " of "),
    ("ints", "k0: interrupts live: IDT 256 | PIC remapped | PIT 100 Hz"),
    ("ready", "k0: scheduler running. type help."),
    ("prompt", "k0> "),
    ("help", "commands: help about mem ticks ps alloc free clear echo heap htest mods run dir cat store ping\n"
             "  alloc  take a 4 KiB frame and write a test pattern\n"
             "  free   give the frame back\n"
             "  heap   heap state: base, free bytes, live blocks, largest block\n"
             "  htest  heap self-test: patterns, reuse, coalescing\n"
             "  ps     the scheduler table with work counters\n"),
    ("about", "K0: boot, console, serial, physical memory, interrupts,\n"
              "keyboard, scheduler, shell, heap, module runner,\n"
              "filesystem, framebuffer console and network driver -\n"
              "all written in Krell.\n"
              "The machine layer is twelve services in boot.s.\n"),
    ("unknown", "unknown command: "),
    ("exc", "EXCEPTION vector "),
    ("halt", " - halted"),
    ("ticksa", "ticks "),
    ("ticksb", " | uptime "),
    ("pshdr", "tasks (work counters):\n"),
    ("t0", "shell"),
    ("t1", "clock"),
    ("t2", "beat"),
    ("t3", "spinner"),
    ("alloca", "frame at "),
    ("allocb", " - pattern verified\n"),
    ("allocbad", " - PATTERN MISMATCH\n"),
    ("allocnone", "alloc: no free frames\n"),
    ("freeda", "freed frame at "),
    ("freenone", "free: nothing to free\n"),
    ("chelp", "help"),
    ("cabout", "about"),
    ("cmem", "mem"),
    ("cticks", "ticks"),
    ("cps", "ps"),
    ("calloc", "alloc"),
    ("cfree", "free"),
    ("cclear", "clear"),
    ("cecho", "echo"),
    ("heapr", "k0: heap ready: "),
    ("heaprb", " bytes at "),
    ("heapa", "heap: base "),
    ("heapb", " free "),
    ("heapc", " live "),
    ("heapd", " largest "),
    ("htp1", "htest: patterns ok"),
    ("htp2", "htest: reuse ok"),
    ("htp3", "htest: PASS"),
    ("htf", "htest: FAIL"),
    ("cheap", "heap"),
    ("chtest", "htest"),
    ("modok", "k0: modules in ramdisk: "),
    ("modsa", "modules: "),
    ("modsb", " bytes at "),
    ("cmods", "mods"),
    ("hk1", "kprint"),
    ("hk2", "kputn"),
    ("hk3", "kputc"),
    ("hk4", "kticks"),
    ("hk5", "kalloc"),
    ("hk6", "kfree"),
    ("hmain", "main"),
    ("crun", "run"),
    ("cdir", "dir"),
    ("ccat", "cat"),
    ("cstore", "store"),
    ("nodisk", "no disk\n"),
    ("fsdisk", "k0: filesystem: "),
    ("fskfs", "k0fs, "),
    ("fsfiles", " files, "),
    ("fsfree", " sectors free\n"),
    ("fsnone", "none\n"),
    ("fsbytes", " bytes\n"),
    ("cping", "ping"),
    ("netpre", "k0: network: "),
    ("netmac", "e1000 mac "),
    ("netip", " ip 10.0.2.15\n"),
    ("netno", "no network\n"),
    ("pingok", "reply from 10.0.2.2: icmp_seq=1\n"),
    ("pingno", "ping: no reply\n"),
    ("fbpre", "k0: framebuffer: "),
    ("fbx", "x"),
    ("fbbpp", ", 32 bpp, text "),
    ("fbcols", "x"),
    ("fbend", "\n"),
    ("catno", "cat: no such file\n"),
    ("storeuse", "usage: store <name> <text>\n"),
    ("storefull", "store: disk full\n"),
    ("runpre", "run: "),
    ("runexit", "exit "),
    ("runfault", "module fault "),
    ("runuse", "usage: run <index>\n"),
    ("runno", "run: no such module\n"),
]

TAB_PLAIN = [
    0, 0, 49, 50, 51, 52, 53, 54, 55, 56, 57, 48, 45, 61, 0, 0,
    113, 119, 101, 114, 116, 121, 117, 105, 111, 112, 91, 93, 0, 0,
    97, 115, 100, 102, 103, 104, 106, 107, 108, 59, 39, 96, 0, 92,
    122, 120, 99, 118, 98, 110, 109, 44, 46, 47, 0, 0, 0, 32,
]
TAB_SHIFT = [
    0, 0, 33, 64, 35, 36, 37, 94, 38, 42, 40, 41, 95, 43, 0, 0,
    81, 87, 69, 82, 84, 89, 85, 73, 79, 80, 123, 125, 0, 0,
    65, 83, 68, 70, 71, 72, 74, 75, 76, 58, 34, 126, 0, 124,
    90, 88, 67, 86, 66, 78, 77, 60, 62, 63, 0, 0, 0, 32,
]
SPIN = [124, 47, 45, 92]

assert len(TAB_PLAIN) == 58 and len(TAB_SHIFT) == 58

blobs = []  # (accessor, [bytes])
for name, text in STRINGS:
    blobs.append((name, list(text.encode("ascii")) + [0]))
# 8x16 bitmap font for the framebuffer console, rendered from
# DejaVu Sans Mono: glyphs for characters 32..127, 16 bytes each,
# one byte per row, MSB = leftmost pixel.
def _make_font():
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 16)
    out = []
    for ch in range(32, 128):
        img = Image.new("L", (10, 20), 0)
        d = ImageDraw.Draw(img)
        d.text((0, -2), chr(ch), fill=255, font=f)
        img = img.resize((8, 16))
        for y in range(16):
            byte = 0
            for x in range(8):
                if img.getpixel((x, y)) > 100:
                    byte |= 1 << (7 - x)
            out.append(byte)
    return out

FONT = _make_font()
blobs.append(("font", FONT))
blobs.append(("spin", SPIN))
blobs.append(("tab1", TAB_PLAIN))
blobs.append(("tab2", TAB_SHIFT))

out = []
for idx, (name, data) in enumerate(blobs):
    body = ", ".join(str(b) for b in data)
    out.append(f"data d_{name}: i8 = {{ {body} }}")
    out.append(f"fn s_{name}() -> ptr {{")
    out.append("  entry():")
    out.append(f"    %p = dataptr {idx}")
    out.append("    ret %p")
    out.append("}")
    out.append("")

t1 = (HERE / "kernel_t1.krell").read_text()
t2 = (HERE / "kernel_t2.krell").read_text()
# The shell dispatch (exec_line) and main sit after the subsystem
# templates so every command handler is defined before its caller;
# each template is also written callee-first internally.
marker = "fn exec_line() -> void {"
head2, tail2 = t2.split(marker, 1)
parts = [t1.replace("@@DATA@@", "\n".join(out)), head2]
for extra in ("kernel_t3.krell", "kernel_t4.krell",
              "kernel_t5.krell", "kernel_t6.krell"):
    f = HERE / extra
    if f.exists():
        parts.append(f.read_text())
parts.append(marker + tail2)
src = "".join(parts)
(HERE / "kernel.krell").write_text(src)
print(f"kernel.krell: {len(src)} bytes, {src.count(chr(10))} lines, "
      f"{len(blobs)} data blobs")
