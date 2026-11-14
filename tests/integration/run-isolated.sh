#!/usr/bin/env bash
# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
set -euo pipefail
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
script_ref=${1:-"$repo_root/../brewpi-script-rmx"}
panel_ref=${2:-"$repo_root/../brewpi-www-rmx"}
evidence=${3:-"$repo_root/runs/milestone4/$(date -u +%Y%m%dT%H%M%SZ)-$$"}
image=${RMX_INTEGRATION_IMAGE:-brewpi-emulator-m4-tools:local}
script_ref=$(CDPATH= cd -- "$script_ref" && pwd)
panel_ref=$(CDPATH= cd -- "$panel_ref" && pwd)
mkdir -p -- "$(dirname -- "$evidence")"
# Reserve atomically. A prior run's result or serial history is never reusable.
if ! mkdir -- "$evidence"; then
    printf '%s\n' 'Evidence directory must be new; existing contents were not changed.' >&2
    exit 2
fi
evidence=$(CDPATH= cd -- "$evidence" && pwd)
finish() {
    result=$?
    trap - EXIT
    if [ -s "$evidence/container.cid" ]; then
        container_id=$(cat "$evidence/container.cid")
        docker stop --time 15 "$container_id" >/dev/null 2>&1 || true
        docker rm -f "$container_id" >/dev/null 2>&1 || true
    fi
    if [ "$result" -ne 0 ]; then
        if [ -f "$evidence/integration-results.json" ]; then
            mv "$evidence/integration-results.json" "$evidence/integration-before-launcher-failure.json"
        fi
        printf '{"status":"failed","stage":"launcher","exit_code":%d}\n' "$result" > "$evidence/integration-results.json"
    fi
    if [ "$result" -eq 0 ]; then status=passed; else status=failed; fi
    printf '{"status":"%s","exit_code":%d}\n' "$status" "$result" > "$evidence/launcher-results.json"
    exit "$result"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Build context contains original test tooling only, never reference applications.
docker build -t "$image" -f "$repo_root/tests/integration/Dockerfile" "$repo_root/tests/integration"
docker image inspect "$image" > "$evidence/image-inspect.json"
docker run --rm --init --cidfile "$evidence/container.cid" --network none --shm-size 256m --tmpfs /lab:exec \
    -v "$repo_root:/work:ro" -v "$script_ref:/refs/script:ro" \
    -v "$panel_ref:/refs/panel:ro" -v "$evidence:/evidence" \
    "$image" timeout --signal=TERM --kill-after=20 900 python3 -u /work/tests/integration/run.py
