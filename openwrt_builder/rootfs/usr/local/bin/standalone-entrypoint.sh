#!/bin/sh
set -eu

# Export runtime paths used by API and runner.
set -a
. /etc/openwrt-builder/paths.env
set +a

for var_name in \
  OPENWRT_BUILDER_LISTS_DIR \
  OPENWRT_BUILDER_FILES_DIR \
  OPENWRT_BUILDER_PROFILES_DIR \
  OPENWRT_BUILDER_BUILDS_DIR \
  OPENWRT_BUILDER_CACHE_DIR \
  OPENWRT_BUILDER_RUNTIME_DIR
do
  eval "dir=\${$var_name}"
  if [ -n "${dir:-}" ]; then
    mkdir -p -- "$dir"
  fi
done

export PYTHONPATH="/app/openwrt-builder:${PYTHONPATH:-}"

printf "\033[32mINFO\033[0m Starting OpenWRT ImageBuilder runner (standalone)\n"
python3 -m openwrt_builder.runner.main &

printf "\033[32mINFO\033[0m Starting OpenWRT ImageBuilder API (standalone)\n"
exec python3 -m openwrt_builder.main
