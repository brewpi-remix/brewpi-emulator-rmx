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
command -v python3 >/dev/null
python3 -c 'import os; exec("if not __debug__ or os.environ.get(\"PYTHONOPTIMIZE\",\"\") not in (\"\",\"0\"):\n raise SystemExit(\"Python assertions must be enabled\")")'
payload_args=(-e RMX_EXECUTION_MODE=source-build)
case ${RMX_EXECUTION_MODE:-source-build} in
    source-build) [ -z "${RMX_PAYLOAD_ROOT:-}${RMX_PAYLOAD_MANIFEST:-}" ] || exit 2 ;;
    packaged-input)
        payload_root=$(CDPATH= cd -- "${RMX_PAYLOAD_ROOT:?}" && pwd)
        payload_manifest=$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve(strict=True))' "${RMX_PAYLOAD_MANIFEST:?}")
        payload_args=(-v "$payload_root:/payload:ro" -v "$payload_manifest:/payload-manifest.json:ro"
            -e "RMX_CANDIDATE_COMMIT=${RMX_CANDIDATE_COMMIT:-}" -e "RMX_CANDIDATE_SNAPSHOT=${RMX_CANDIDATE_SNAPSHOT:-}" -e RMX_EXECUTION_MODE=packaged-input -e RMX_PAYLOAD_ROOT=/payload -e RMX_PAYLOAD_MANIFEST=/payload-manifest.json) ;;
    *) exit 2 ;;
esac
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
    trap '' INT TERM
    set +e
    cleanup_ok=yes
    if [ -s "$evidence/container.cid" ]; then
        container_id=$(cat "$evidence/container.cid")
        docker stop --time 15 "$container_id" >> "$evidence/container-cleanup.log" 2>&1
        docker rm -f "$container_id" >> "$evidence/container-cleanup.log" 2>&1
        remaining=$(docker ps -aq --no-trunc --filter "id=$container_id" 2>> "$evidence/container-cleanup.log")
        if [ "$?" -ne 0 ] || [ -n "$remaining" ]; then cleanup_ok=no; fi
    elif [ "$result" -eq 0 ]; then
        cleanup_ok=no
    fi
    python3 "$repo_root/tests/qualification/evidence.py" "$evidence" "$result" "$cleanup_ok" integration
    exit $?
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Build context contains original test tooling only, never reference applications.
case ${RMX_INTEGRATION_SKIP_BUILD:-0} in
    0) docker build -t "$image" -f "$repo_root/tests/integration/Dockerfile" "$repo_root/tests/integration" ;;
    1) ;; # Explicitly reuse an existing tool image; record its actual immutable ID.
    *) printf '%s\n' 'RMX_INTEGRATION_SKIP_BUILD must be 0 or 1.' >&2; exit 2 ;;
esac
image_id=$(docker image inspect --format '{{.Id}}' "$image")
docker image inspect "$image_id" > "$evidence/image-inspect.json"
docker run --rm --init --cidfile "$evidence/container.cid" --network none --shm-size 256m --tmpfs /lab:exec \
    "${payload_args[@]}" -v "$repo_root:/work:ro" -v "$script_ref:/refs/script:ro" \
    -v "$panel_ref:/refs/panel:ro" -v "$evidence:/evidence" \
    "$image_id" timeout --signal=TERM --kill-after=20 900 python3 -u /work/tests/integration/run.py
