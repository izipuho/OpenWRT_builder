#!/usr/bin/with-contenv bashio
set -euo pipefail

python3 /usr/local/bin/health_server.py &

# TODO: тут запускай основной процесс аддона
tail -f /dev/null
