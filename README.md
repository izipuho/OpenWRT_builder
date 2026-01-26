# OpenWRT HA ImageBuilder (Home Assistant Add-on)

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

1. Configure the add-on settings (target, profile, packages).
2. Start the add-on.
3. Wait for the build to complete.
4. Download the generated firmware image.

## Notes

- ImageBuilder runs inside the add-on container.
- The add-on does not flash devices automatically; it only builds firmware images.

## License

MIT

