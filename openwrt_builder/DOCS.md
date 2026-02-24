# Documentation — OpenWRT HA ImageBuilder Add-on

## Overview

OpenWRT HA ImageBuilder is a Home Assistant add-on that provides a reproducible environment for building custom OpenWrt firmware images using the official OpenWrt ImageBuilder.

The add-on is intended to be used as a **build backend** for Home Assistant integrations or external workflows. It does **not** flash devices and does **not** manage routers directly.

## Architecture

- The add-on runs OpenWrt ImageBuilder inside an isolated container.
- Build parameters are provided via add-on configuration (or by a Home Assistant integration).
- Build artifacts are stored in the add-on data directory and exposed for download.
- One add-on instance can be reused for multiple builds sequentially.

## What the Add-on Does

- Downloads and prepares OpenWrt ImageBuilder for the selected target.
- Builds firmware images with:
  - selected device profile
  - included packages
  - excluded packages
- Outputs standard OpenWrt firmware artifacts.

## What the Add-on Does NOT Do

- Flash firmware to devices.
- Discover or manage OpenWrt routers.
- Modify running systems.
- Replace OpenWrt ASU (Attended Sysupgrade).


## Configuration

Typical configuration parameters:

- **target**  
  OpenWrt target (e.g. `ath79/generic`, `mediatek/filogic`).

- **profile**  
  Device profile supported by ImageBuilder.

- **packages**  
  List of packages to include.

- **packages_exclude**  
  List of packages to explicitly exclude.

- **output_format**  
  Image format produced by ImageBuilder (depends on target).

Exact schema depends on the add-on version and UI configuration.

## Build Process

1. Add-on receives build configuration.
2. ImageBuilder is prepared (downloaded or reused from cache).
3. `make image` is executed with provided parameters.
4. Logs are streamed to the add-on log output.
5. Resulting firmware files are stored in the output directory.

## Output Artifacts

Depending on target and profile, outputs may include:

- `.bin`
- `.img.gz`
- `.tar.gz`
- `.manifest`

Artifacts are intended to be:
- downloaded manually
- consumed by a Home Assistant integration
- uploaded to an OpenWrt device via sysupgrade


## Standalone Deployment

A ready-to-run compose template is available:

- `openwrt_builder/docker-compose.standalone.yml`

Quick start:

```bash
cd openwrt_builder
docker compose -f docker-compose.standalone.yml up -d --build
```

For internet-facing installs, set `OPENWRT_BUILDER_CORS_ORIGINS` in your shell environment or project `.env` to explicit UI hostnames.

## Integration with Home Assistant

This add-on is designed to work well with:

- custom Home Assistant integrations
- automated OpenWrt build workflows
- profile-based firmware management

A typical pattern:

- Integration prepares build parameters.
- Integration triggers the add-on.
- Integration retrieves artifacts and manages deployment separately.

## Limitations

- Only one build runs at a time.
- Requires sufficient disk space.
- Build time depends on target and package set.
- Supported targets are limited to official OpenWrt ImageBuilder releases.

## Troubleshooting

- **Build fails early**  
  Check target/profile compatibility.

- **Missing packages**  
  Verify package names for the selected OpenWrt release.

- **Out of space**  
  Increase available storage for the add-on.

- **Unsupported target**  
  Ensure the target exists in the selected OpenWrt version.

## License

MIT License.
