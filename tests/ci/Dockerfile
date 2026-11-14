# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
# External tools only. Snapshot timestamp and base index are immutable inputs.
FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3
RUN rm -f /etc/apt/sources.list.d/debian.sources && printf '%s\n' 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20261113T000000Z bookworm main' 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20261113T000000Z bookworm-security main' > /etc/apt/sources.list && apt-get update && apt-get install -y --no-install-recommends g++ cmake make python3 git ca-certificates binutils && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1
