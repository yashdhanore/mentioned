#!/usr/bin/env sh
set -eu

exec fastapi run src/main.py --host 0.0.0.0 --port "${PORT:-10000}"
