#!/bin/sh
# Pre-commit step: run the latency regression check.
set -e
root="$(git rev-parse --show-toplevel)"
cd "$root"
make --no-print-directory bench-check
