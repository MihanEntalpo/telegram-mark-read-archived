#!/usr/bin/env bash
set -euo pipefail

docker compose up --force-recreate -d archive_read_service
cid=$(docker compose ps -q archive_read_service)

docker logs "$cid"
docker attach "$cid"
