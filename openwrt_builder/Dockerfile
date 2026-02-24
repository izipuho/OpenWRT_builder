ARG BUILD_FROM=python:3.12-alpine
FROM $BUILD_FROM AS runtime

RUN apk add --no-cache bash openssl python3 py3-pip build-base make tar xz zstd perl curl jq \
    findutils diffutils gawk grep gzip unzip bzip2 wget
RUN pip3 install --no-cache-dir fastapi uvicorn pydantic python-multipart

COPY rootfs /
COPY imagebuilder-wrapper /app/imagebuilder-wrapper

FROM runtime AS standalone
RUN chmod +x /usr/local/bin/standalone-entrypoint.sh
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/standalone-entrypoint.sh"]

FROM runtime AS ha-addon
