[![Publish container to ghcr.io](https://github.com/samsonnguyen/docker-brother-mfc-l27x0dw/actions/workflows/publish.yml/badge.svg)](https://github.com/samsonnguyen/docker-brother-mfc-l27x0dw/actions/workflows/publish.yml)
[![ghcr.io](https://img.shields.io/badge/ghcr.io-samsonnguyen%2Fdocker--brother--mfc--l27x0dw-blue?logo=docker)](https://github.com/samsonnguyen/docker-brother-mfc-l27x0dw/pkgs/container/docker-brother-mfc-l27x0dw)

All-in-one container running `cupsd` plus `brscan-skey`, so the scan buttons on the
printer's own panel work as well as printing.

Available on GHCR: [`ghcr.io/samsonnguyen/docker-brother-mfc-l27x0dw`](https://github.com/samsonnguyen/docker-brother-mfc-l27x0dw/pkgs/container/docker-brother-mfc-l27x0dw)

> The old Docker Hub repository is no longer published. Pull from GHCR.

Tested only with:

* MFC-L2700DW

Duplex scanning and PDF assembly were originally inspired by
[arjunkc/scanner-scripts](https://github.com/arjunkc/scanner-scripts).

# Usage

```
docker run --env-file=.env --net=host -it ghcr.io/samsonnguyen/docker-brother-mfc-l27x0dw:latest
```

`--net=host` is required: the printer opens a connection back to the container on
`54925/udp`, and `brscan-skey` advertises its own address. Under Kubernetes this
means `hostNetwork: true`.

The Brother drivers are i386/amd64 only, so the image does not run on arm64 nodes.

# Configuration

Everything is resolved at runtime, in this order (last wins):

1. built-in defaults (below)
2. `/etc/brother/scan.yaml`
3. environment variables

`brscan-skey` forks a fresh process for each button press, so the config is re-read
on **every scan**. Mounting `scan.yaml` from a ConfigMap means `kubectl edit configmap`
changes the next scan — no pod restart, no rollout. Environment changes need a
restart, so prefer the file for anything you expect to tune.

The image ships [`etc/brother/scan.yaml`](etc/brother/scan.yaml) at
`/etc/brother/scan.yaml`, annotated and pre-filled for an MFC-L2700DW at
`192.168.1.62`. Override the printer settings for your own network.

## Scan keys

The panel has four fixed destinations — `file`, `ocr`, `email`, `image`. The
hardware decides the names; the config decides what each one does.

Shipped defaults:

| Key | duplex | mode | resolution | source |
| --- | --- | --- | --- | --- |
| `file` | no | `Gray[Error Diffusion]` | 300 | ADF |
| `ocr` | yes | `Gray[Error Diffusion]` | 300 | ADF duplex |
| `email` | yes | `24bit Color[Fast]` | 300 | ADF duplex |
| `image` | no | `24bit Color[Fast]` | 300 | ADF |

All four also inherit `width: 215.88`, `height: 279.4` (US Letter, mm) and
`batch_threshold: 10m`.

### Per-key fields

| Field | Default | Notes |
| --- | --- | --- |
| `resolution` | `300` | 100, 150, 200, 300, 400, 600, 1200… |
| `mode` | `Gray[Error Diffusion]` | must match the driver's string exactly |
| `duplex` | `false` | selects the ADF source automatically |
| `source` | auto | only to override that automatic choice |
| `width` / `height` | `215.88` / `279.4` | millimetres |
| `batch_threshold` | `10m` | window to press the same key again for side two |

Anything under `keys:` overrides `defaults:` for that key alone:

```yaml
defaults:
  resolution: 300
  mode: Gray[Error Diffusion]
  duplex: false

keys:
  ocr:
    duplex: true
  image:
    mode: 24bit Color[Fast]
    resolution: 600
```

Durations accept plain seconds or a suffix: `600`, `10m`, `72h`, `1d`.

## Environment variables

| Variable | Sets | Default |
| --- | --- | --- |
| `MODEL` | printer model | — (required) |
| `PRINTER_NAME` | CUPS queue name | falls back to `MODEL` |
| `PRINTER_IP` | printer address | — (required) |
| `DEVICE_NAME` | SANE device name | falls back to `PRINTER_NAME` |
| `PAGE_SIZE` | CUPS queue default page size | `Letter` |
| `SAVETO` | where PDFs land | `/scans` |
| `LOGDIR` | brscan-skey logs | `/var/log/brother` |
| `SCAN_OPEN_DELAY` | pause before opening a network scanner | `1s` |
| `SCAN_ATTEMPTS` | retries for a pass that scanned nothing | `2` |
| `SCAN_DEFAULT_<FIELD>` | one field, every key | — |
| `SCAN_<KEY>_<FIELD>` | one field, one key | — |
| `SUPERVISOR_RECYCLE_INTERVAL` | brscan-skey-exe recycle | `72h` |
| `SUPERVISOR_RESTART_DELAY` | wait before restarting a dead service | `5s` |
| `SUPERVISOR_SCAN_GRACE` | `SIGTERM` wait for an in-flight scan | `60s` |

`<KEY>` is `FILE`, `OCR`, `EMAIL` or `IMAGE`; `<FIELD>` is any per-key field above.
Per-key beats default — `SCAN_OCR_RESOLUTION=600` raises only OCR.

## In Kubernetes

```yaml
persistence:
  brother-config:
    type: configMap
    name: brother-printer-scan-config
    globalMounts:
      - path: /etc/brother/scan.yaml
        subPath: scan.yaml
```

Use `subPath` so the rest of `/etc/brother/` is left intact, and **never mount at
`/config`** — the CUPS base image already claims that path as its volume.

## Checking what is in effect

```bash
docker exec [container] python3 -c \
  "from brother import config as c; cfg = c.load(); \
   [print(k, c.scan_profile(cfg, k)) for k in c.SCAN_KEYS]"
```

Two things to watch for:

* `mode` is passed to `scanimage` verbatim, so a typo fails at scan time rather
  than at startup. List the values the scanner accepts with
  `scanimage -d 'brother4:net1;dev0' -h`.
* Because config is read per scan, a broken file surfaces on the next button
  press. Run the command above after editing.

# Printer

Access the CUPS server at [http://127.0.0.1:631](http://127.0.0.1:631), or print from any
CUPS client over `631/tcp`. The queue is registered whenever `cupsd` starts, so a
`cupsd` restart cannot leave the container without a printer.

The queue default page size is set from `printer.page_size` (`Letter` by default).
The Brother PPD ships `*DefaultPageSize: A4`, so without this every job comes out
A4 — 297mm against Letter's 279mm, which overruns the sheet. Setting it by hand
with `lpadmin` does not survive a restart: `/etc/cups` is not persisted, so the
queue is rebuilt from config on every start.

# Scanner

```
# test the scanner
scanimage -d 'brother4:net1;dev0' -T

# view all available options
docker exec [container] scanimage -d 'brother4:net1;dev0' -h
```

Scans land in the `/scans` volume as a single PDF per job.

Each key writes to `<SAVETO>/<key>-<timestamp>.pdf`, with the individual page
scans kept under `<SAVETO>/<key>/<timestamp>/`.

See [Scan keys](#scan-keys) for what each button does and how to change it.

Duplex is two passes. Press the key, let the fronts feed, flip the stack, press the
same key again within `batch_threshold` (10m default); the backs are interleaved
into reading order and the whole document is written as one PDF. Press a different
key, wait out the threshold, or lose the first pass's files and the pending job is
abandoned rather than resumed.

# Driver installation

Brother's `linux-brprinter-installer` does two things a plain `dpkg -i` does not,
both of which this image now replicates:

* **32-bit runtime.** The LPR driver is i386, and the CUPS filter chain ends in
  `rawtobr3` / `brprintconflsr3`. Without a 32-bit loader those exit 0 and emit
  nothing, so CUPS reports every job as successful while printing blank. The image
  installs `lib32stdc++6` (which pulls `libc6-i386`) and the build fails if
  `/lib/ld-linux.so.2` is missing.
* **`/etc/init.d` stubs.** The installer symlinks `cups`, `cupsys`, `lpd` and
  `lprng` to `/bin/true` so the packages' `postinst` service restarts succeed.

The packages are installed with `--force-architecture` only — the i386 drivers are
genuinely foreign-arch, but nothing else is forced, so a real failure fails the
build. `brscan-skey` declares a dependency on `curl`, which is installed rather
than forced past, and `apt-get check` gates the layer.

A build-time smoke test pushes a PostScript job through
`brother_lpdwrapper_MFCL2700DW` and fails unless it produces a PJL stream. This
class of breakage is silent at runtime, so it is caught at build time instead.

# Process supervision

`brscan-skey-exe` is a closed-source Brother binary that segfaults in
`register_pc_legacy` — its periodic "register this PC with the MFC" keep-alive —
after almost exactly 85 hours of uptime, on a clock that resets when the process
starts. Confirmed across 30 consecutive crashes, all at the same fault address.

It used to be the container's foreground process, so each crash took `cupsd` and the
whole container down with it. Now PID 1 is a supervisor that runs `cupsd` and
`brscan-skey-exe` independently:

* `brscan-skey-exe` is recycled every `recycle_interval` (72h default) so the fault
  never fires, and is restarted if it dies anyway
* recycles are deferred while a scan holds the lock
* `cupsd` is unaffected by either
* `SIGTERM` waits up to `scan_grace` for an in-flight scan before stopping

Keep `scan_grace` below the pod's `terminationGracePeriodSeconds`, or the kubelet
will `SIGKILL` first. A `preStop` hook running `brscan-skey -t` is no longer needed
and will just cause an extra restart.

# Tests

```
bash tests/run.sh
```

Builds the image, starts it as production does, and runs `tests/test-drivers.sh`
against the live `cupsd`. A temporary queue on the stock `socket` backend points
at a local capture server, so a real job is spooled, filtered and delivered — the
bytes land in a file instead of on paper. It asserts the backend received a PJL
stream, which is the only check that catches the failure mode where the i386
filters emit nothing and CUPS still reports the job complete.

The production queue uses `ipp://`, so this covers the filter chain and spooling
rather than the ipp backend. It also verifies the SANE backend loads with all
libraries resolved, and that no package dependencies are unsatisfied.

CI runs it before publishing.
