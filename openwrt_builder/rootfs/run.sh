#!/command/with-contenv sh
set -euo pipefail

python3 /usr/local/bin/health_server.py &

# TODO: тут запускай основной процесс аддона
echo "OpenWRT ImageBuilder addon started"
sleep infinity
