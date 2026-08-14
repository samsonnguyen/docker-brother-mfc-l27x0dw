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

1. built-in defaults
2. `/etc/brother/scan.yaml`
3. environment variables

`brscan-skey` forks a fresh process for each button press, so the config is re-read
on every scan. Mounting `scan.yaml` from a ConfigMap means `kubectl edit configmap`
changes the next scan — no pod restart, no rollout.

See [`etc/brother/scan.yaml`](etc/brother/scan.yaml) for the full annotated file.

```yaml
printer:
  model: Brother-MFC-L2700DW
  ip: 192.168.1.62

defaults:
  resolution: 300
  mode: Gray[Error Diffusion]

keys:
  ocr:
    duplex: true
  image:
    mode: 24bit Color[Fast]
    resolution: 600
```

Do not mount it at `/config` — the CUPS base image already uses that path.

## Environment variables

| Variable | Sets |
| --- | --- |
| `MODEL`, `PRINTER_NAME`, `PRINTER_IP`, `DEVICE_NAME` | printer identity |
| `SAVETO`, `LOGDIR` | output and log locations |
| `SCAN_DEFAULT_<FIELD>` | a scan field for every key |
| `SCAN_<KEY>_<FIELD>` | a scan field for one key, e.g. `SCAN_OCR_RESOLUTION=600` |
| `SUPERVISOR_RECYCLE_INTERVAL` | how often to recycle `brscan-skey-exe` |
| `SUPERVISOR_SCAN_GRACE` | how long `SIGTERM` waits for an in-flight scan |

`<FIELD>` is one of `resolution`, `width`, `height`, `mode`, `source`, `duplex`,
`batch_threshold`. Per-key beats default.

# Printer

Access the CUPS server at [http://127.0.0.1:631](http://127.0.0.1:631), or print from any
CUPS client over `631/tcp`. The queue is registered whenever `cupsd` starts, so a
`cupsd` restart cannot leave the container without a printer.

# Scanner

```
# test the scanner
scanimage -d 'brother4:net1;dev0' -T

# view all available options
docker exec [container] scanimage -d 'brother4:net1;dev0' -h
```

Scans land in the `/scans` volume as a single PDF per job.

## Scan keys

The panel offers four fixed destinations. What each one does is entirely config —
the table below is only the shipped default.

| Key | duplex | mode | resolution |
| --- | --- | --- | --- |
| `scantofile` | no | Gray[Error Diffusion] | 300 |
| `scantoocr` | yes | Gray[Error Diffusion] | 300 |
| `scantoemail` | yes | 24bit Color[Fast] | 300 |
| `scantoimage` | no | 24bit Color[Fast] | 300 |

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
