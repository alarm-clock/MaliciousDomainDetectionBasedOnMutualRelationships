#!/bin/sh
set -eu

python3 /usr/local/bin/render-config-templates
exec "$@"
