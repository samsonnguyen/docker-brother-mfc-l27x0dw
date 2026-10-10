"""Pull tinted paper to white on grayscale pages.

Coloured paper scans as mid-grey. Stretching the page so its brightest 2% lands on
white fixes that when the paper is most of the page. A page that already has real
white paper (letters, photo sheets) is left essentially unchanged, and nothing local
is touched, so photographs keep their tones. White paper reads close to 255 on this
scanner already, so for ordinary documents this is close to a no-op.
"""

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("scan")

# Debian ships ImageMagick 6 (`convert`); newer installs only provide `magick`.
IMAGEMAGICK = shutil.which("magick") or shutil.which("convert")

WHITE_CLIP = "2%"


def is_gray_mode(mode):
    return "gray" in str(mode).lower()


def stretch_white(path):
    """Apply the white point to one JPEG in place. A failure leaves the original page untouched."""
    if not IMAGEMAGICK:
        log.warning("ImageMagick not found — skipping white point")
        return False

    source = Path(path)
    scratch = source.with_name(source.stem + ".white.jpg")

    result = subprocess.run(
        [
            IMAGEMAGICK, str(source),
            "-contrast-stretch", f"0x{WHITE_CLIP}",
            "-colorspace", "Gray", "-quality", "90",
            str(scratch),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not scratch.exists():
        log.warning("white point failed for %s: %s", source.name, result.stderr.strip())
        scratch.unlink(missing_ok=True)
        return False

    scratch.replace(source)
    return True
