# OpenWRT ImageBuilder (Home Assistant Add-on + Standalone)

Home Assistant add-on that runs OpenWrt ImageBuilder and allows building custom OpenWrt firmware images based on selected profiles and device targets.

## Features

- Build custom OpenWrt images using ImageBuilder.
- Support for build profiles (package lists, include/exclude rules).
- Generation of firmware artifacts (`.bin`, `.img.gz`, etc.) ready for flashing.
- Build logs available via the add-on interface.

## Requirements

- Home Assistant OS or Home Assistant Supervised (HA OS recommended).
- Internet access to download ImageBuilder and packages (unless using a local cache).
- Sufficient disk space for build artifacts.

## Usage

1. Start the add-on.
2. Open the add-on ingress web UI.
3. Configure build inputs in the UI (OpenWrt version, target/subtarget, platform/profile, package lists/files).
4. Run the build and download the generated firmware image.

## Notes

- ImageBuilder runs inside the add-on container.
- The add-on does not flash devices automatically; it only builds firmware images.
- Home Assistant add-on `options`/`schema` are intentionally empty in the current implementation.
- Build parameters are configured inside the ingress web UI and stored in the add-on data directory.

## License

MIT

## Build Modes

- Home Assistant add-on mode uses `openwrt_builder/Dockerfile` with Home Assistant base images from `openwrt_builder/build.yaml`.
- Standalone Docker mode uses `openwrt_builder/Dockerfile.standalone` via `openwrt_builder/docker-compose.standalone.yml`.
- These paths are intentionally separated so standalone changes do not affect HA add-on compatibility.


## Run in standalone mode

```bash
cd openwrt_builder
docker compose -f docker-compose.standalone.yml up -d --build
```

Then open `http://localhost:8081` (the compose file maps host port 8081 to container port 8080). For production, set `OPENWRT_BUILDER_CORS_ORIGINS` via shell environment or project `.env` to your real UI hostname(s).

## Convert External Package Lists

If you have package lists from another ImageBuilder project (for example `lists/` from a cloned repository), convert them into this project's list format:

```bash
python3 openwrt_builder/tools/convert_imagebuilder_lists.py \
  --source-dir /path/to/imagebuilder/lists \
  --output-dir openwrt_builder/data/lists \
  --dry-run
```

When output looks correct, run again without `--dry-run` (and add `--overwrite` if needed).


## Standalone: current implementation summary

- Standalone launch is provided via `openwrt_builder/docker-compose.standalone.yml`.
- Core runtime path variables are loaded inside the container from `/etc/openwrt-builder/paths.env`.
- CORS is controlled by `OPENWRT_BUILDER_CORS_ORIGINS` (comma-separated origins).
- If `OPENWRT_BUILDER_CORS_ORIGINS` is empty/unset, fallback is permissive (`*`).
- For internet-facing setups, explicitly set `OPENWRT_BUILDER_CORS_ORIGINS` to your real UI origin(s).
