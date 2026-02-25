#!/bin/sh
set -eu

. /usr/local/lib/openwrt-builder/common.sh

mode="${1:-}"
if [ -z "$mode" ]; then
  printf "ERROR: mode is required (api|runner|standalone)\n" >&2
  exit 1
fi

owb_load_paths_env
owb_export_pythonpath

api_module="openwrt_builder.main"
runner_module="openwrt_builder.runner.main"
main_module=""
main_log=""

case "$mode" in
  api)
    owb_ensure_runtime_dirs
    main_module="$api_module"
    main_log="OpenWRT ImageBuilder API manager started"
  ;;
  runner)
    main_module="$runner_module"
    main_log="OpenWRT ImageBuilder runner started"
  ;;
  standalone)
    owb_ensure_runtime_dirs
    printf "\033[32mINFO\033[0m Starting OpenWRT ImageBuilder runner (standalone)\n"
    python3 -m "$runner_module" &
    main_module="$api_module"
    main_log="Starting OpenWRT ImageBuilder API (standalone)"
  ;;
  *)
    printf "ERROR: unknown mode '%s' (expected: api|runner|standalone)\n" "$mode" >&2
    exit 1
  ;;
esac

printf "\033[32mINFO\033[0m %s\n" "$main_log"
exec python3 -m "$main_module"
