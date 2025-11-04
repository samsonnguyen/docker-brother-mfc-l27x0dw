#!/bin/bash
set -e
saved=("$@")
set --

echo "Starting cupsd"
cupsd
lpadmin -p "${PRINTER_NAME}" -E -v "ipp://${PRINTER_IP}" -m brother-MFCL2710DW-cups-en.ppd
echo `lpstat -p "${PRINTER_NAME}" -l`
lpoptions -d "${PRINTER_NAME}"

brsaneconfig4 -a name="${DEVICE_NAME}" model=${MODEL} ip=${PRINTER_IP}

set -- ${saved[*]}
exec "$@"
