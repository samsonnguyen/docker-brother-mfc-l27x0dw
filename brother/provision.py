"""One-time setup driven by the runtime config: scanner registration, the
generated brscan-skey.config, and (once cupsd answers) the CUPS queue."""

import glob
import logging
import shlex
import subprocess
from pathlib import Path

from . import config as configlib

log = logging.getLogger("provision")

SKEY_DIR = Path("/opt/brother/scanner/brscan-skey")
SKEY_CONFIG = SKEY_DIR / "brscan-skey.config"
SCAN_ENTRYPOINT = "/usr/bin/brother-scan"


def _run(argv, check=False):
    log.info("running %s", " ".join(shlex.quote(a) for a in argv))
    result = subprocess.run(argv, capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    if output:
        log.info("%s: %s", argv[0], output)
    if check and result.returncode != 0:
        raise SystemExit(f"{argv[0]} failed with exit {result.returncode}")
    return result


def find_ppd(config):
    configured = config["printer"].get("ppd")
    if configured:
        return configured

    matches = sorted(glob.glob("/opt/brother/Printers/*/cupswrapper/*.ppd"))
    if not matches:
        raise SystemExit("no Brother PPD found under /opt/brother/Printers")
    if len(matches) > 1:
        log.warning("multiple PPDs found, using %s", matches[0])
    return matches[0]


def render_skey_config(config):
    """brscan-skey reads this at startup; every key points at the same entrypoint."""
    scanner = config["scanner"]
    lines = [f"password={config['printer'].get('password') or ''}"]
    for key in configlib.SCAN_KEYS:
        lines.append(f'{key.upper()}="{SCAN_ENTRYPOINT} {key}"')
    lines += [
        "SEMID=b",
        f'SAVETO="{scanner["saveto"]}"',
        f'LOGDIR="{scanner["logdir"]}"',
        "",
    ]

    Path(scanner["logdir"]).mkdir(parents=True, exist_ok=True)
    Path(scanner["saveto"]).mkdir(parents=True, exist_ok=True)
    SKEY_CONFIG.write_text("\n".join(lines))
    log.info("wrote %s", SKEY_CONFIG)


def configure_scanner(config):
    printer = config["printer"]
    _run([
        "brsaneconfig4",
        "-a",
        f"name={printer['device_name']}",
        f"model={printer['model']}",
        f"ip={printer['ip']}",
    ])


def cups_ready():
    # `lpstat -r` exits 0 whether or not the scheduler is up, so its exit code
    # says nothing; only the text distinguishes the two.
    result = subprocess.run(["lpstat", "-r"], capture_output=True, text=True)
    return result.returncode == 0 and "not running" not in result.stdout.lower()


def register_printer(config):
    printer = config["printer"]
    argv = [
        "lpadmin",
        "-p", printer["name"],
        "-E",
        "-v", f"ipp://{printer['ip']}",
        "-P", find_ppd(config),
    ]
    # Without this the PPD's own *DefaultPageSize (A4) wins, and CUPS is holding
    # the only copy of the queue — /etc/cups is not persisted, so it has to be
    # reapplied on every start rather than set once by hand.
    if printer.get("page_size"):
        argv += ["-o", f"PageSize={printer['page_size']}"]
    _run(argv)
    _run(["lpoptions", "-d", printer["name"]])
    _run(["lpstat", "-p", printer["name"], "-l"])


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = configlib.load()
    configlib.require_printer(config)
    render_skey_config(config)
    configure_scanner(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
