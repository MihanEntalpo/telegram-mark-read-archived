#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME=${IMAGE_NAME:-telegram-auto-read}

docker build -t "${IMAGE_NAME}" .
