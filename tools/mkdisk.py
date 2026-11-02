#!/usr/bin/env python3
"""Create a k0fs disk image for K0.

Layout (512-byte sectors):
  LBA 0        superblock
  LBA 1..64    directory: 8 entries per sector, 64 bytes per entry
               (name 48 bytes NUL-padded, start LBA i64 at +48,
               length i64 at +56; an entry is used iff start != 0)
  LBA 65..     file data, bump-allocated

Superblock (i64 fields): magic "K0FS" at byte 0 (u32),
  total_sectors +8, dir_start +16, dir_sectors +24,
  data_start +32, bump +40, file_count +48.
"""
import struct, sys

SECTORS = 8192            # 4 MiB
DIR_START, DIR_SECTORS = 1, 64
DATA_START = DIR_START + DIR_SECTORS

img = bytearray(SECTORS * 512)

def put_file(off_slot, name, content: bytes, lba):
    e = DIR_START * 512 + off_slot * 64
    nb = name.encode()
    assert len(nb) < 48
    img[e:e + len(nb)] = nb
    struct.pack_into("<q", img, e + 48, lba)
    struct.pack_into("<q", img, e + 56, len(content))
    img[lba * 512:lba * 512 + len(content)] = content
    return lba + (len(content) + 511) // 512

bump = DATA_START
bump = put_file(0, "readme.txt",
                b"k0fs: files on an ATA disk, managed from Krell.\n"
                b"store writes a file; it persists across boots.\n", bump)

struct.pack_into("<I", img, 0, 0x5346304B)  # "K0FS" little-endian bytes K 0 F S
struct.pack_into("<q", img, 8, SECTORS)
struct.pack_into("<q", img, 16, DIR_START)
struct.pack_into("<q", img, 24, DIR_SECTORS)
struct.pack_into("<q", img, 32, DATA_START)
struct.pack_into("<q", img, 40, bump)
struct.pack_into("<q", img, 48, 1)

out = sys.argv[1] if len(sys.argv) > 1 else "disk.img"
open(out, "wb").write(img)
print(f"{out}: {SECTORS} sectors, data starts at {DATA_START}, bump {bump}")
