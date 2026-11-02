#!/usr/bin/env python3
"""Regenerate kernel/font.inc, the framebuffer console font.

Renders DejaVu Sans Mono at 16 px with Pillow: glyphs for
characters 32..127, each downsampled to 8x16, one byte per
row, MSB = leftmost pixel, threshold 100. Output is 1536
byte values as comma-separated decimal text. This is a
maintainer tool, not part of the build: the kernel build
reads the checked-in font.inc and needs no font renderer.
"""
import pathlib

HERE = pathlib.Path(__file__).parent
OUT = HERE.parent / "kernel" / "font.inc"
TTF = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def main():
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(TTF, 16)
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
    assert len(out) == 1536
    lines = [", ".join(str(b) for b in out[i:i + 16])
             for i in range(0, 1536, 16)]
    OUT.write_text(",\n".join(lines) + "\n")
    print(f"font.inc: {len(out)} bytes -> {OUT}")


if __name__ == "__main__":
    main()
