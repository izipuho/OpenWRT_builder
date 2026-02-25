ARG BUILD_FROM=python:3.12-alpine
FROM $BUILD_FROM AS runtime

RUN apk add --no-cache bash openssl python3 py3-pip build-base make tar xz zstd perl curl jq \
    findutils diffutils gawk grep gzip unzip bzip2 wget
RUN pip3 install --no-cache-dir fastapi uvicorn pydantic python-multipart

COPY rootfs /

FROM runtime AS standalone
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/openwrt-builder-launcher.sh", "standalone"]

FROM runtime AS ha-addon
