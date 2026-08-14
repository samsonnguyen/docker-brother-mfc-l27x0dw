#!/bin/bash
# Verifies the Brother drivers work through a running cupsd, without printing.
#
# A temporary queue using the stock socket backend points at a local capture
# server, so a real job is spooled, filtered and handed to a backend exactly as
# production does — only the bytes land in a file instead of on paper. The
# production queue uses ipp:// rather than socket://, so this covers the filter
# chain and spooling, not the ipp backend itself.
#
# Run inside an already-running container: docker exec <c> /tests/test-drivers.sh

set -uo pipefail

QUEUE=driver-selftest
PORT=${CAPTURE_PORT:-9100}
CAPTURED=/tmp/captured.prn
JOB=/tmp/selftest.ps
PPD=$(ls /opt/brother/Printers/*/cupswrapper/*.ppd 2>/dev/null | head -1)

failures=0
pass() { echo "  PASS  $1"; }
fail() { echo "  FAIL  $1"; failures=$((failures + 1)); }
check() { if [ "$1" = 0 ]; then pass "$2"; else fail "$2${3:+ — $3}"; fi; }

cleanup() {
    lpadmin -x "$QUEUE" 2>/dev/null
    [ -n "${capture_pid:-}" ] && kill "$capture_pid" 2>/dev/null
    rm -f "$CAPTURED" "$JOB"
}
trap cleanup EXIT

echo "=== 1. cupsd is up and the production queue is registered ==="
lpstat -r >/dev/null 2>&1
check $? "cupsd is accepting requests"

production_queue=$(lpstat -p 2>/dev/null | awk '/^printer/ {print $2}' | head -1)
if [ -n "$production_queue" ]; then
    pass "queue registered: $production_queue"
    lpstat -p "$production_queue" 2>/dev/null | grep -q "disabled"
    if [ $? -eq 0 ]; then fail "$production_queue is disabled"; else pass "$production_queue is enabled"; fi
else
    fail "no printer queue registered"
fi

echo
echo "=== 2. the Brother PPD is installed and parses ==="
if [ -n "$PPD" ]; then
    pass "PPD found: $PPD"
    grep -q "brother_lpdwrapper" "$PPD"
    check $? "PPD routes through the Brother filter"
else
    fail "no Brother PPD under /opt/brother/Printers"
fi

echo
echo "=== 3. the filter chain is executable ==="
wrapper=$(grep -o 'brother_lpdwrapper_[A-Za-z0-9]*' "$PPD" 2>/dev/null | head -1)
[ -x "/usr/lib/cups/filter/$wrapper" ]
check $? "/usr/lib/cups/filter/$wrapper is executable"

test -x /lib/ld-linux.so.2
check $? "32-bit loader present (i386 driver binaries can exec)" \
      "install lib32stdc++6"

for binary in $(find /opt/brother/Printers -type f -name 'rawtobr3' -o -name 'brprintconflsr3'); do
    "$binary" </dev/null >/dev/null 2>/tmp/binerr
    if grep -qi "no such file or directory\|cannot execute\|not found" /tmp/binerr; then
        fail "$(basename "$binary") cannot execute: $(head -1 /tmp/binerr)"
    else
        pass "$(basename "$binary") executes"
    fi
done

echo
echo "=== 4. a real job through cupsd reaches the backend ==="
python3 /tests/capture-server.py 127.0.0.1 "$PORT" "$CAPTURED" >/tmp/capture.log 2>&1 &
capture_pid=$!
for _ in $(seq 20); do grep -q listening /tmp/capture.log && break; sleep 0.2; done

lpadmin -p "$QUEUE" -E -v "socket://127.0.0.1:$PORT" -P "$PPD" 2>/tmp/lpadmin.err
check $? "temporary queue created" "$(head -1 /tmp/lpadmin.err 2>/dev/null)"

printf '%%!PS\n/Helvetica findfont 24 scalefont setfont 72 700 moveto (driver selftest) show showpage\n' > "$JOB"
lp -d "$QUEUE" "$JOB" >/tmp/lp.out 2>&1
check $? "job submitted" "$(head -1 /tmp/lp.out)"

for _ in $(seq 60); do
    [ -z "$(lpstat -o "$QUEUE" 2>/dev/null)" ] && break
    sleep 0.5
done

if [ -n "$(lpstat -o "$QUEUE" 2>/dev/null)" ]; then
    fail "job never left the queue: $(lpstat -o "$QUEUE" | head -1)"
else
    pass "job completed and left the queue"
fi

wait "$capture_pid" 2>/dev/null
capture_pid=""

if [ -s "$CAPTURED" ]; then
    pass "backend received $(wc -c < "$CAPTURED") bytes"
else
    fail "backend received 0 bytes (filters produced nothing)"
fi

grep -q '@PJL' "$CAPTURED" 2>/dev/null
check $? "output is a PJL job stream (driver actually rendered)"

if grep -qi "aborted\|stopped" <(lpstat -W completed -o "$QUEUE" 2>/dev/null); then
    fail "job reported aborted/stopped"
else
    pass "job not aborted"
fi

echo
echo "=== 5. scanner driver loads ==="
backend=$(ls /usr/lib/*/sane/libsane-brother4.so.1 /usr/lib64/sane/libsane-brother4.so.1 2>/dev/null | head -1)
if [ -n "$backend" ]; then
    pass "brother4 backend present: $backend"
    missing=$(ldd "$backend" 2>/dev/null | grep "not found")
    if [ -n "$missing" ]; then
        fail "backend has unresolved libraries: $(echo "$missing" | tr '\n' ' ')"
    else
        pass "backend shared libraries all resolve"
    fi
else
    fail "libsane-brother4 not installed"
fi

grep -qx "brother4" /etc/sane.d/dll.conf
check $? "brother4 enabled in /etc/sane.d/dll.conf"

brsaneconfig4 -q >/dev/null 2>&1
check $? "brsaneconfig4 runs"

echo
echo "=== 6. package state is consistent ==="
apt-get check >/dev/null 2>&1
check $? "no unsatisfied package dependencies"

echo
if [ "$failures" -eq 0 ]; then
    echo "ALL DRIVER CHECKS PASSED"
else
    echo "$failures CHECK(S) FAILED"
fi
exit "$failures"
