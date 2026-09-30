"""Render the editable architecture SVG with an already-installed CPU renderer."""
from pathlib import Path
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    source, output = ROOT / "docs/architecture.svg", ROOT / "docs/architecture.png"
    tree = ET.parse(source)
    assert tree.getroot().get("viewBox") == "0 0 720 530"
    renderer = shutil.which("rsvg-convert")
    if renderer is None:
        raise SystemExit("Install/provide rsvg-convert separately; this script installs nothing.")
    subprocess.run([renderer, "--output", str(output), str(source)], check=True)
    raw = output.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", raw[16:24]) != (720, 530):
        raise SystemExit("Unexpected architecture PNG dimensions")
    print("Rendered docs/architecture.png (720x530); inspect actual pixels at 360px.")


if __name__ == "__main__":
    main()
