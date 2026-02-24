ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache bash python3 py3-pip build-base make tar xz zstd perl curl jq
RUN pip3 install --no-cache-dir fastapi uvicorn pydantic python-multipart

COPY rootfs /
COPY imagebuilder-wrapper /app/imagebuilder-wrapper
