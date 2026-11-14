#!/usr/bin/env bash
# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
set -euo pipefail
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
evidence=${1:-"$repo_root/runs/milestone5/$(date -u +%Y%m%dT%H%M%SZ)-$$"}
image=${RMX_QUALIFICATION_IMAGE:-brewpi-emulator-m4-tools:portable}
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
if ! mkdir -- "$evidence"; then
    printf '%s\n' 'Qualification evidence directory must be new.' >&2
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
    python3 "$repo_root/tests/qualification/evidence.py" "$evidence" "$result" "$cleanup_ok"
    exit $?
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
architecture=$(docker image inspect --format '{{.Architecture}}' "$image")
[ "$architecture" = "${RMX_TARGET_ARCH:-arm64}" ] || { printf '%s\n' 'Image architecture differs from requested target.' >&2; exit 2; }
image_id=$(docker image inspect --format '{{.Id}}' "$image")
docker image inspect "$image_id" > "$evidence/image-inspect.json"
docker run --rm --init --cidfile "$evidence/container.cid" --network none --shm-size 256m --tmpfs /qualification:exec \
    "${payload_args[@]}" -e RMX_DISPOSABLE_QUALIFICATION=1 -e "RMX_TARGET_ARCH=${RMX_TARGET_ARCH:-arm64}" -v "$repo_root:/work:ro" -v "$evidence:/evidence" \
    "$image_id" timeout --signal=TERM --kill-after=20 900 python3 -u /work/tests/qualification/prepare.py
