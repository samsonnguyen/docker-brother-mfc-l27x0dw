"""Flatten uneven paper tone on grayscale pages.

Coloured or tinted paper scans as mid-grey and shades unevenly toward the edges.
Dividing the page by an estimate of the paper (a blurred, dilated copy built at a
quarter of the resolution) brings the paper to white and leaves ink untouched.
White paper is already near 255 on this scanner, so there it is close to a no-op.
"""

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("scan")

# Debian ships ImageMagick 6 (`convert`); newer installs only provide `magick`.
IMAGEMAGICK = shutil.which("magick") or shutil.which("convert")

ESTIMATE_SCALE = 25


def is_gray_mode(mode):
    return "gray" in str(mode).lower()


def _dimensions(path):
    width, height = subprocess.run(
        ["identify", "-format", "%w %h", f"{path}[0]"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    return int(width), int(height)


def flatten_page(path):
    """Flatten one JPEG in place. A failure leaves the original page untouched."""
    if not IMAGEMAGICK:
        log.warning("ImageMagick not found — skipping page flatten")
        return False

    source = Path(path)
    scratch = source.with_name(source.stem + ".flat.jpg")

    try:
        width, height = _dimensions(source)
        result = subprocess.run(
            [
                IMAGEMAGICK, str(source),
                "(", "+clone",
                "-resize", f"{ESTIMATE_SCALE}%", "-blur", "0x1",
                "-morphology", "Dilate", "Disk:3", "-blur", "0x5",
                "-resize", f"{width}x{height}!", ")",
                "-fx", "min(1,u/max(v,0.05))",
                "-colorspace", "Gray", "-quality", "90",
                str(scratch),
            ],
            capture_output=True, text=True,
        )
    except (subprocess.CalledProcessError, ValueError) as error:
        log.warning("page flatten failed for %s: %s", source.name, error)
        return False

    if result.returncode != 0 or not scratch.exists():
        log.warning("page flatten failed for %s: %s", source.name, result.stderr.strip())
        scratch.unlink(missing_ok=True)
        return False

    scratch.replace(source)
    return True
