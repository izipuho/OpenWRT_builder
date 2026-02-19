ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip build-base make tar xz zstd perl
RUN pip3 install --no-cache-dir fastapi uvicorn pydantic python-multipart

COPY rootfs /
COPY imagebuilder-wrapper /app/imagebuilder-wrapper
