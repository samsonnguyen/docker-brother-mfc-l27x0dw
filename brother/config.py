"""Runtime configuration: builtin defaults < config file < environment."""

import os
import re
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    yaml = None

# Not /config — the CUPS base image already claims that path as its volume.
CONFIG_PATH = Path(os.environ.get("BROTHER_CONFIG", "/etc/brother/scan.yaml"))

SCAN_KEYS = ("file", "ocr", "email", "image")

ADF_DUPLEX = "Automatic Document Feeder(left aligned,Duplex)"
ADF_SIMPLEX = "Automatic Document Feeder(left aligned)"

BUILTIN = {
    # The Brother PPD ships *DefaultPageSize: A4, so the queue default has to be
    # set explicitly or every job comes out A4 regardless of the paper loaded.
    "printer": {
        "model": None,
        "name": None,
        "ip": None,
        "device_name": None,
        "page_size": "Letter",
    },
    "scanner": {
        "saveto": "/scans",
        "logdir": "/var/log/brother",
        "sane_device": None,
        # Brother's own scripts pause before opening a network device and retry
        # once if nothing came out; the scanner is still finishing its side of
        # the button press and rejects an early open with "Invalid argument".
        "open_delay": "1s",
        "attempts": 2,
    },
    # brscan-skey-exe segfaults in register_pc_legacy at ~85h of uptime, every
    # time. Recycling well short of that keeps the fault from ever firing.
    "supervisor": {
        "recycle_interval": "72h",
        "restart_delay": "5s",
        "scan_grace": "60s",
    },
    "defaults": {
        "resolution": 300,
        "width": 215.88,
        "height": 279.4,
        "mode": "Gray[Error Diffusion]",
        "source": None,
        "duplex": False,
        "batch_threshold": "10m",
    },
    "keys": {
        "file": {"duplex": False},
        "ocr": {"duplex": True},
        "email": {"mode": "24bit Color[Fast]", "duplex": True},
        "image": {"mode": "24bit Color[Fast]", "duplex": False},
    },
}

_DURATION = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhd]?)\s*$", re.IGNORECASE)
_MULTIPLIER = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}


def duration(value):
    """Accept 3600, "3600", "90m", "72h" — always returns seconds as a float."""
    if isinstance(value, (int, float)):
        return float(value)
    match = _DURATION.match(str(value))
    if not match:
        raise ValueError(f"invalid duration: {value!r}")
    return float(match.group(1)) * _MULTIPLIER[match.group(2).lower()]


def boolean(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _deep_merge(base, overlay):
    merged = dict(base)
    for key, value in (overlay or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _from_file(path):
    if not path.exists():
        return {}
    text = path.read_text()
    if yaml is None:
        raise RuntimeError(f"{path} exists but PyYAML is unavailable")
    return yaml.safe_load(text) or {}


# Field name -> the environment suffix that overrides it. Scan fields are
# addressable per key (SCAN_OCR_RESOLUTION) and globally (SCAN_DEFAULT_RESOLUTION).
_SCAN_FIELDS = ("resolution", "width", "height", "mode", "source", "duplex", "batch_threshold")


def _env_scan_overrides(prefix):
    found = {}
    for field in _SCAN_FIELDS:
        value = os.environ.get(f"SCAN_{prefix}_{field}".upper())
        if value is not None:
            found[field] = value
    return found


def load():
    config = _deep_merge(BUILTIN, _from_file(CONFIG_PATH))

    for section, field, var in (
        ("printer", "model", "MODEL"),
        ("printer", "name", "PRINTER_NAME"),
        ("printer", "ip", "PRINTER_IP"),
        ("printer", "device_name", "DEVICE_NAME"),
        ("printer", "page_size", "PAGE_SIZE"),
        ("scanner", "saveto", "SAVETO"),
        ("scanner", "logdir", "LOGDIR"),
        ("scanner", "sane_device", "SANE_DEVICE"),
        ("scanner", "open_delay", "SCAN_OPEN_DELAY"),
        ("scanner", "attempts", "SCAN_ATTEMPTS"),
        ("supervisor", "recycle_interval", "SUPERVISOR_RECYCLE_INTERVAL"),
        ("supervisor", "restart_delay", "SUPERVISOR_RESTART_DELAY"),
        ("supervisor", "scan_grace", "SUPERVISOR_SCAN_GRACE"),
    ):
        value = os.environ.get(var)
        if value:
            config[section][field] = value

    config["defaults"] = _deep_merge(config["defaults"], _env_scan_overrides("DEFAULT"))
    for key in SCAN_KEYS:
        config["keys"][key] = _deep_merge(
            config["keys"].get(key, {}), _env_scan_overrides(key)
        )

    if not config["printer"]["name"]:
        config["printer"]["name"] = config["printer"]["model"]
    if not config["printer"]["device_name"]:
        config["printer"]["device_name"] = config["printer"]["name"]

    return config


def scan_profile(config, key):
    if key not in SCAN_KEYS:
        raise SystemExit(f"unknown scan key {key!r}; expected one of {', '.join(SCAN_KEYS)}")

    profile = _deep_merge(config["defaults"], config["keys"].get(key, {}))
    profile["duplex"] = boolean(profile["duplex"])
    profile["resolution"] = int(profile["resolution"])
    profile["width"] = float(profile["width"])
    profile["height"] = float(profile["height"])
    profile["batch_threshold"] = duration(profile["batch_threshold"])

    if not profile.get("source"):
        profile["source"] = ADF_DUPLEX if profile["duplex"] else ADF_SIMPLEX

    profile["key"] = key
    return profile


def require_printer(config):
    missing = [
        field for field in ("model", "name", "ip") if not config["printer"].get(field)
    ]
    if missing:
        raise SystemExit(
            "missing required printer config: "
            + ", ".join(missing)
            + f" (set via {CONFIG_PATH} or MODEL/PRINTER_NAME/PRINTER_IP)"
        )
