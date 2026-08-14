#!/bin/bash
set -e

# The CUPS base image sets up /config and runs its init.d hooks here. It ends
# with `$@`, so clear the arguments before sourcing and restore them after.
saved=("$@")
set --
source "${PREFIX}/bin/docker-entrypoint.sh"
set -- "${saved[@]}"

python3 -m brother.provision

exec "$@"
