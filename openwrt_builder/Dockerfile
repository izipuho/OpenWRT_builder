ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache bash openssl python3 py3-pip build-base make tar xz zstd perl curl jq
RUN mkdir -p /builder/shared-workdir/build/staging_dir/host/etc/ssl \
    && cp /etc/ssl/openssl.cnf /builder/shared-workdir/build/staging_dir/host/etc/ssl/openssl.cnf
RUN pip3 install --no-cache-dir fastapi uvicorn pydantic python-multipart

COPY rootfs /
COPY imagebuilder-wrapper /app/imagebuilder-wrapper
