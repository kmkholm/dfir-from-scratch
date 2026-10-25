"""Chapter 02 - File signatures and carving."""

from __future__ import annotations

import io
import random
import struct
import zipfile
import zlib
from pathlib import Path

from .._samples import GIF, JPEGS
from ..core import Chapter, Question, sha256_bytes

SECTOR = 512
IMAGE_SIZE = 1 << 20  # 1 MiB

SIGNATURES = {
    "jpeg": b"\xff\xd8\xff",
    "png": b"\x89PNG\r\n\x1a\n",
    "pdf": b"%PDF-",
    "zip": b"PK\x03\x04",
    "gif": b"GIF89a",
}

# 5x7 bitmap glyphs for the code word drawn into the PNG.
GLYPHS = {
    "A": [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "C": [" ####", "#    ", "#    ", "#    ", "#    ", "#    ", " ####"],
    "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    "F": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"],
    "P": ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
    "X": ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    "Y": ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "3": ["#### ", "    #", "    #", " ### ", "    #", "    #", "#### "],
    "4": ["#   #", "#   #", "#   #", "#####", "    #", "    #", "    #"],
    "7": ["#####", "    #", "   # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "    #", " ### "],
}

PLACES = ["pier 7", "the old mill", "gate C", "platform 4", "the north car park", "warehouse 12"]


def make_png(code: str, scale: int = 6) -> bytes:
    """Grayscale PNG showing `code` in a blocky font. Pure zlib, no Pillow."""
    pad, gap = 2, 1
    cols = pad * 2 + len(code) * 5 + (len(code) - 1) * gap
    rows = pad * 2 + 7
    grid = [[235] * cols for _ in range(rows)]
    for i, ch in enumerate(code):
        x0 = pad + i * (5 + gap)
        for y, line in enumerate(GLYPHS[ch]):
            for x, px in enumerate(line):
                if px == "#":
                    grid[pad + y][x0 + x] = 25
    raw = bytearray()
    for row in grid:
        line = bytes(v for v in row for _ in range(scale))
        for _ in range(scale):
            raw += b"\x00" + line
    width, height = cols * scale, rows * scale

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")


def _pdf_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(lines) -> bytes:
    """Single-page PDF with a correct xref table."""
    text = ["BT", "/F1 14 Tf", "72 720 Td"]
    for i, line in enumerate(lines):
        if i:
            text.append("0 -22 Td")
        text.append(f"({_pdf_escape(line)}) Tj")
    text.append("ET")
    stream = "\n".join(text).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def make_zip(note: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo("note.txt", date_time=(2026, 2, 11, 23, 5, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, (note + "\n") * 3)
    return buf.getvalue()


def _noise(rng: random.Random, n: int) -> bytes:
    # Printable junk (0x20-0x7e) looks like leftover text and can never form
    # a binary signature by accident.
    return bytes(rng.randint(0x20, 0x7E) for _ in range(n))


def _count(data: bytes, sig: bytes) -> int:
    return data.count(sig)


def _build(rng: random.Random):
    n_jpeg = rng.randint(2, 5)
    code = "".join(rng.choice(sorted(GLYPHS)) for _ in range(5))
    note = f"Meet at {rng.choice(PLACES)} at {rng.randint(20, 23)}:{rng.choice(['05', '15', '30', '40', '50'])}. Bring the second phone."
    pdf = make_pdf(["Quarterly summary - INTERNAL", f"Ref {rng.randint(10000, 99999)}", "Do not forward."])
    png = make_png(code)
    zipped = make_zip(note)
    items = [("jpeg", j) for j in rng.sample(JPEGS, n_jpeg)] + [("png", png), ("pdf", pdf), ("zip", zipped), ("gif", GIF)]
    rng.shuffle(items)

    img = bytearray()
    placed = []
    # Leave room at the start like a boot area / filesystem metadata.
    img += bytes(SECTOR * rng.randint(4, 16))
    for kind, blob in items:
        gap_sectors = rng.randint(2, 40)
        img += _noise(rng, gap_sectors * SECTOR) if rng.random() < 0.6 else bytes(gap_sectors * SECTOR)
        placed.append((kind, len(img), blob))
        img += blob
        tail = (-len(img)) % SECTOR       # pad to next sector with slack
        img += bytes(tail)
    if len(img) > IMAGE_SIZE:
        raise ValueError("image overflow")
    img += _noise(rng, (IMAGE_SIZE - len(img)) // 2)
    img += bytes(IMAGE_SIZE - len(img))
    return bytes(img), placed, code, note, n_jpeg, png, zipped


def _inbox(rng: random.Random, out: Path) -> str:
    """A handful of files whose extensions lie. Exactly one is really a PDF."""
    inbox = out / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    real = {
        "png": make_png("".join(rng.choice(sorted(GLYPHS)) for _ in range(3)), 2),
        "jpeg": rng.choice(JPEGS),
        "zip": make_zip("nothing to see here"),
        "gif": GIF,
        "txt": b"shopping: milk, eggs, batteries\n",
        "pdf": make_pdf(["Shipping manifest", f"Container {rng.randint(100000, 999999)}"]),
    }
    disguises = ["holiday.jpg", "contract.pdf", "budget.xlsx", "song.mp3", "readme.txt", "scan_0012.png", "minutes.docx"]
    rng.shuffle(disguises)
    kinds = list(real)
    rng.shuffle(kinds)
    pdf_name = None
    for name, kind in zip(disguises, kinds):
        # never let a file tell the truth about itself
        if (kind, name.rsplit(".", 1)[1]) in {("pdf", "pdf"), ("png", "png"), ("jpeg", "jpg"), ("txt", "txt")}:
            name = name.rsplit(".", 1)[0] + ".dat"
        (inbox / name).write_bytes(real[kind])
        if kind == "pdf":
            pdf_name = name
    return pdf_name


def generate(rng: random.Random, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    for _ in range(50):
        img, placed, code, note, n_jpeg, png, zipped = _build(rng)
        expected_counts = {"jpeg": n_jpeg, "png": 1, "pdf": 1, "zip": 1, "gif": 1}
        if all(_count(img, SIGNATURES[k]) == v for k, v in expected_counts.items()):
            break
    else:  # pragma: no cover - would need astronomically bad luck
        raise RuntimeError("could not build a clean image")

    (out / "disk.img").write_bytes(img)
    pdf_offset = next(off for kind, off, _ in placed if kind == "pdf")
    pdf_name = _inbox(rng, out)
    return {
        "jpeg_count": n_jpeg,
        "pdf_offset": pdf_offset,
        "png_code": code,
        "png_sha256": sha256_bytes(png),
        "zip_note": note,
        "inbox_pdf": pdf_name,
    }


CHAPTER = Chapter(
    id="02",
    slug="carving",
    title="Magic bytes: file signatures and carving",
    summary="Recover deleted files from a raw disk image by their signatures, and unmask files with lying extensions.",
    brief=(
        "A suspect formatted a 1 MiB partition before handing it over. The filesystem is gone, but\n"
        "formatting rarely wipes data. disk.img is a raw copy of that partition. A second folder,\n"
        "inbox/, came from the suspect's mail client - the file extensions look suspicious."
    ),
    questions=[
        Question("jpeg_count", "How many complete JPEG images are inside disk.img?", "int"),
        Question("pdf_offset", "At what byte offset does the PDF start? (decimal or 0x-hex)", "int"),
        Question("png_code", "Carve the PNG and open it. What code does it show?"),
        Question("png_sha256", "SHA-256 of the carved PNG (exactly from signature to the end of IEND)", "sha256"),
        Question("zip_note", "Carve the ZIP and read note.txt. What is the first line?"),
        Question("inbox_pdf", "Which file in inbox/ is actually a PDF?"),
    ],
    hints=[
        "Every format starts with fixed 'magic bytes': JPEG ff d8 ff, PNG 89 50 4e 47 0d 0a 1a 0a, "
        "PDF 25 50 44 46 2d (%PDF-), ZIP 50 4b 03 04, GIF 47 49 46 38 39 61. Search the image for them.",
        "Headers tell you where a file starts; you also need where it ends. JPEG ends at ff d9. A PNG ends "
        "4 bytes after the 'IEND' tag (that's the CRC). A ZIP ends with the End of Central Directory record "
        "(50 4b 05 06) plus 22 bytes and the comment length.",
        "Python makes this short: data = open('disk.img','rb').read(); data.find(sig, start). "
        "For inbox/, ignore the names and read the first 8 bytes of every file.",
    ],
    generate=generate,
    tags=["file signatures", "carving", "hex"],
)
