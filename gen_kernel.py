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
    ("help", "commands: help about mem ticks ps alloc free clear echo\n"
             "  alloc  take a 4 KiB frame and write a test pattern\n"
             "  free   give the frame back\n"
             "  ps     the scheduler table with work counters\n"),
    ("about", "K0: boot, console, serial, physical memory, interrupts,\n"
              "keyboard, scheduler and shell - all written in Krell.\n"
              "The machine layer is eight services in boot.s.\n"),
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
src = t1.replace("@@DATA@@", "\n".join(out)) + t2
(HERE / "kernel.krell").write_text(src)
print(f"kernel.krell: {len(src)} bytes, {src.count(chr(10))} lines, "
      f"{len(blobs)} data blobs")
