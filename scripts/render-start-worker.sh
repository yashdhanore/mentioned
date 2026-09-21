#!/usr/bin/env sh
set -eu

# python -m src.worker, not the mentioned-worker console script: the Docker image
# does not install this package (see Dockerfile), so no console script exists.
exec python -m src.worker
