#!/bin/sh

owb_load_paths_env() {
  set -a
  . /etc/openwrt-builder/paths.env
  set +a
}

owb_ensure_runtime_dirs() {
  env | while IFS='=' read -r k v; do
    case "$k" in
      OPENWRT_BUILDER_*_DIR)
        [ -n "$v" ] && mkdir -p -- "$v"
      ;;
    esac
  done
}

owb_export_pythonpath() {
  export PYTHONPATH="/app/openwrt-builder:${PYTHONPATH:-}"
}
