#!/bin/bash
set -e
saved=("$@")
set --
source ${PREFIX}/bin/docker-entrypoint.sh
cupsd
lpadmin -p "${PRINTER_NAME}" -E -v "ipp://${PRINTER_IP}" -m brother-MFCL2710DW-cups-en.ppd
echo `lpstat -p "${PRINTER_NAME}" -l`
lpoptions -d "${PRINTER_NAME}"

brsaneconfig4 -a name="${PRINTER_NAME}" model="MFC-L2700DW" ip=${PRINTER_IP}

set -- ${saved[*]}
echo "TEST"
exec "$@"
