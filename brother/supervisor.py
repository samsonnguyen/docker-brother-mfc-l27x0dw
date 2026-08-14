"""PID 1: keeps cupsd and brscan-skey-exe running independently of each other.

Previously brscan-skey-exe was the container's foreground process, so its
recurring segfault took cupsd and the whole container down with it. Here each
service is restarted on its own, and brscan-skey-exe is recycled on a timer
that stays comfortably below the ~85h mark where it faults.
"""

import errno
import logging
import os
import signal
import subprocess
import time

from . import config as configlib
from . import provision
from .runlock import scan_in_progress

log = logging.getLogger("supervisor")

BRSCAN_SKEY_EXE = "/opt/brother/scanner/brscan-skey/brscan-skey-exe"
POLL_SECONDS = 1.0


class Service:
    def __init__(self, name, argv, recycle_after=None, ready_check=None, on_ready=None):
        self.name = name
        self.argv = argv
        self.recycle_after = recycle_after
        self.ready_check = ready_check
        self.on_ready = on_ready
        self.process = None
        self.started_at = None
        self.restart_at = None
        self.ready_done = False

    def start(self):
        self.process = subprocess.Popen(self.argv)
        self.started_at = time.monotonic()
        self.restart_at = None
        self.ready_done = self.on_ready is None
        log.info("started %s (pid %d)", self.name, self.process.pid)

    @property
    def uptime(self):
        return time.monotonic() - self.started_at if self.started_at else 0.0

    def due_for_recycle(self):
        return self.recycle_after and self.uptime >= self.recycle_after

    def stop(self, sig=signal.SIGTERM):
        if self.process and self.process.poll() is None:
            log.info("sending %s to %s (pid %d)", sig.name, self.name, self.process.pid)
            self.process.send_signal(sig)


def returncode_from_status(status):
    if os.WIFSIGNALED(status):
        return -os.WTERMSIG(status)
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    return None


def describe_exit(process):
    code = process.returncode
    if code is not None and code < 0:
        return f"killed by {signal.Signals(-code).name}"
    return f"exit {code}"


class Supervisor:
    def __init__(self, config):
        self.config = config
        self.shutting_down = False
        self.restart_delay = configlib.duration(config["supervisor"]["restart_delay"])
        self.scan_grace = configlib.duration(config["supervisor"]["scan_grace"])
        recycle = configlib.duration(config["supervisor"]["recycle_interval"])

        # The CUPS queue is (re)registered whenever cupsd comes up, so a cupsd
        # restart cannot leave the container with no printer.
        self.services = [
            Service(
                "cupsd",
                ["cupsd", "-f"],
                ready_check=provision.cups_ready,
                on_ready=lambda: provision.register_printer(config),
            ),
            Service("brscan-skey", [BRSCAN_SKEY_EXE, "-f"], recycle_after=recycle),
        ]

    def handle_signal(self, signum, _frame):
        log.info("received %s — shutting down", signal.Signals(signum).name)
        self.shutting_down = True

    def run(self):
        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)

        for service in self.services:
            service.start()

        while not self.shutting_down:
            self.tick()
            time.sleep(POLL_SECONDS)

        self.shutdown()
        return 0

    def reap(self):
        """PID 1 inherits every orphan in the container, so this process is the
        only reaper. It has to hand each supervised child's status back to its
        Popen — otherwise Popen finds the pid already reaped and reports exit 0,
        losing the signal that killed it."""
        supervised = {s.process.pid: s for s in self.services if s.process}
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return
            except OSError as exc:
                if exc.errno == errno.ECHILD:
                    return
                raise
            if pid == 0:
                return

            service = supervised.get(pid)
            if service is None:
                log.debug("reaped orphan pid %d", pid)
            elif service.process.returncode is None:
                service.process.returncode = returncode_from_status(status)

    def tick(self):
        self.reap()

        now = time.monotonic()
        for service in self.services:
            if service.process.poll() is not None:
                if service.restart_at is None:
                    log.error(
                        "%s died (%s) after %.1fh — restarting in %.0fs",
                        service.name, describe_exit(service.process),
                        service.uptime / 3600, self.restart_delay,
                    )
                    service.restart_at = now + self.restart_delay
                elif now >= service.restart_at:
                    service.start()
                continue

            if not service.ready_done and service.ready_check():
                try:
                    service.on_ready()
                except Exception:
                    log.exception("%s post-start hook failed", service.name)
                service.ready_done = True

            if service.due_for_recycle():
                if scan_in_progress():
                    log.info("%s recycle due but a scan is in flight — deferring", service.name)
                    continue
                log.info(
                    "recycling %s preemptively after %.1fh of uptime",
                    service.name, service.uptime / 3600,
                )
                self.terminate(service)
                service.start()

    def terminate(self, service, timeout=10.0):
        service.stop()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if service.process.poll() is not None:
                return
            time.sleep(0.2)
        log.warning("%s did not exit in %.0fs — killing", service.name, timeout)
        service.stop(signal.SIGKILL)
        try:
            service.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            log.error("%s is unkillable", service.name)

    def shutdown(self):
        deadline = time.monotonic() + self.scan_grace
        while scan_in_progress() and time.monotonic() < deadline:
            log.info("waiting for in-flight scan before shutting down")
            time.sleep(1.0)

        for service in reversed(self.services):
            self.terminate(service)
        log.info("all services stopped")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return Supervisor(configlib.load()).run()


if __name__ == "__main__":
    raise SystemExit(main())
