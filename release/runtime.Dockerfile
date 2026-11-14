# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3
RUN rm -f /etc/apt/sources.list.d/debian.sources /etc/apt/apt.conf.d/docker-clean && printf '%s\n' 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20261113T000000Z bookworm main' 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20261113T000000Z bookworm-security main' > /etc/apt/sources.list && apt-get update && apt-get --download-only install -y --no-install-recommends libstdc++6 libgcc-s1 python3 && mkdir -p /opt/rmx-inputs && sha256sum /var/cache/apt/archives/*.deb > /opt/rmx-inputs/debs.sha256 && apt-get install -y --no-install-recommends libstdc++6 libgcc-s1 python3 && dpkg-query -W > /opt/rmx-inputs/packages.tsv && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*.deb
ENV PYTHONDONTWRITEBYTECODE=1 LC_ALL=C TZ=UTC
