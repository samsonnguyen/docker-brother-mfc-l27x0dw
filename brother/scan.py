#!/usr/bin/env python3
"""Scan pipeline invoked by brscan-skey as `scan.py <key> <sane-device>`.

Replaces the per-key shell scripts: the key selects a profile, everything else
is shared. Duplex is two passes over a flipped stack, correlated through a job
file so the second press of the button finishes the first one's document.
"""

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import img2pdf

from . import config as configlib
from .runlock import scan_lock

log = logging.getLogger("scan")

JOB_FILE = ".job.json"


def batch_dir(saveto, key, timestamp):
    return Path(saveto) / key / str(timestamp)


def batch_template(saveto, key, timestamp):
    directory = batch_dir(saveto, key, timestamp)
    directory.mkdir(parents=True, exist_ok=True)
    return str(directory / f"{key}-part-%03d.jpg")


def scanned_files(template):
    directory = Path(template).parent
    return sorted(str(p) for p in directory.glob(Path(template).name.replace("%03d", "*")))


def run_scanimage(device, profile, template, batch_start, batch_increment,
                  attempts=2, open_delay=1.0):
    argv = [
        "scanimage",
        "--format", "jpeg",
        "--batch=" + template,
        f"--batch-start={batch_start}",
        f"--batch-increment={batch_increment}",
        f"--resolution={profile['resolution']}",
        "--mode", profile["mode"],
        "--source", profile["source"],
        "-x", str(profile["width"]),
        "-y", str(profile["height"]),
    ]
    if device:
        argv[1:1] = ["-d", device]

    before = set(scanned_files(template))

    for attempt in range(1, max(1, attempts) + 1):
        # The MFC is still finishing its own side of the button press when the
        # script fires; opening the device too early fails with "Invalid
        # argument". Brother's scripts pause the same way for net devices.
        if open_delay and device and "net" in device:
            time.sleep(open_delay)

        log.info("running %s", " ".join(argv))
        result = subprocess.run(argv, capture_output=True, text=True)
        if result.stderr.strip():
            log.info("scanimage: %s", result.stderr.strip())
        # scanimage exits non-zero once the feeder runs dry, which is the normal
        # end of a batch rather than a failure.
        if result.returncode != 0:
            log.debug("scanimage exited %s", result.returncode)

        files = scanned_files(template)
        if set(files) - before:
            return files

        if attempt < attempts:
            log.warning(
                "scanimage produced no pages (attempt %d/%d) — retrying",
                attempt, attempts,
            )

    return scanned_files(template)


def page_number(path):
    stem = Path(path).stem
    digits = stem.rsplit("-", 1)[-1]
    return int(digits) if digits.isdigit() else 0


def interleave_duplex(files):
    """Evens were scanned from a flipped stack, so they arrive in reverse order."""
    odds = [f for f in files if page_number(f) % 2 == 1]
    evens = [f for f in files if page_number(f) % 2 == 0]
    evens.reverse()

    if abs(len(odds) - len(evens)) > 1:
        log.warning(
            "duplex page count mismatch: %d odd vs %d even — output may be misordered",
            len(odds), len(evens),
        )

    ordered = []
    for pair in zip(odds, evens):
        ordered.extend(pair)
    ordered.extend(odds[len(evens):])
    return ordered


class Job:
    def __init__(self, saveto):
        self.path = Path(saveto) / JOB_FILE
        try:
            self.state = json.loads(self.path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            self.state = {}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state))
        tmp.replace(self.path)

    def clear(self):
        self.state = {}
        self.save()

    def is_active(self, key, now, threshold):
        if self.state.get("key") != key or not self.state.get("timestamp"):
            return False

        age = now - int(self.state["timestamp"])
        if age > threshold:
            log.info("previous job is %ds old (threshold %ds) — starting fresh", age, threshold)
            return False

        files = self.state.get("files") or []
        missing = [f for f in files if not os.path.exists(f)]
        if not files or missing:
            log.warning(
                "previous job references %d/%d missing files — starting fresh",
                len(missing), len(files),
            )
            return False
        return True


def combine(files, saveto, key, timestamp):
    output = Path(saveto) / f"{key}-{timestamp}.pdf"
    log.info("combining %d pages into %s", len(files), output)
    pdf = img2pdf.convert(files)
    tmp = output.with_suffix(".pdf.partial")
    tmp.write_bytes(pdf)
    # The inotify sidecar ships on close_write/moved_to, so build the PDF out of
    # the watched name and move it in once complete.
    tmp.replace(output)
    log.info("wrote %s", output)
    return output


def main(argv):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if len(argv) < 2:
        raise SystemExit(f"usage: {argv[0]} <{'|'.join(configlib.SCAN_KEYS)}> [sane-device]")

    config = configlib.load()
    key = argv[1]
    profile = configlib.scan_profile(config, key)
    device = argv[2] if len(argv) > 2 else config["scanner"].get("sane_device")
    saveto = config["scanner"]["saveto"]
    attempts = int(config["scanner"]["attempts"])
    open_delay = configlib.duration(config["scanner"]["open_delay"])
    now = int(time.time())

    log.info(
        "scan key=%s duplex=%s resolution=%s mode=%r device=%s",
        key, profile["duplex"], profile["resolution"], profile["mode"], device or "(default)",
    )

    with scan_lock():
        job = Job(saveto)

        if not profile["duplex"]:
            template = batch_template(saveto, key, now)
            files = run_scanimage(device, profile, template, batch_start=1, batch_increment=1,
                                   attempts=attempts, open_delay=open_delay)
            if not files:
                log.error("no pages scanned — nothing to combine")
                return 1
            combine(files, saveto, key, now)
            return 0

        if job.is_active(key, now, profile["batch_threshold"]):
            timestamp = int(job.state["timestamp"])
            template = batch_template(saveto, key, timestamp)
            before = set(scanned_files(template))
            files = run_scanimage(device, profile, template, batch_start=2, batch_increment=2,
                                   attempts=attempts, open_delay=open_delay)

            if not set(files) - before:
                log.warning("second pass scanned 0 pages — finalizing as single-sided")
                ordered = sorted(before)
            else:
                ordered = interleave_duplex(files)

            job.clear()
            combine(ordered, saveto, key, timestamp)
            return 0

        template = batch_template(saveto, key, now)
        files = run_scanimage(device, profile, template, batch_start=1, batch_increment=2,
                              attempts=attempts, open_delay=open_delay)
        if not files:
            log.error("first pass produced no pages — aborting job")
            job.clear()
            return 1

        job.state = {"key": key, "timestamp": now, "files": files}
        job.save()
        log.info(
            "first pass complete (%d pages) — flip the stack and press %s again within %ds",
            len(files), key, int(profile["batch_threshold"]),
        )
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
