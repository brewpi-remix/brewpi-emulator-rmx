# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
# External integration tools only; no reference sources enter this image.
FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3
RUN rm -f /etc/apt/sources.list.d/debian.sources && printf '%s\n' 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20261113T000000Z bookworm main' 'deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20261113T000000Z bookworm-security main' > /etc/apt/sources.list && apt-get update && apt-get install -y --no-install-recommends g++ cmake make git python3-venv python3-dev php-cli php-mbstring chromium ca-certificates binutils systemd && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/brewpi-test
COPY requirements.lock /tmp/test-requirements.lock
RUN /opt/brewpi-test/bin/pip install --disable-pip-version-check --require-hashes -r /tmp/test-requirements.lock
ENV PATH="/opt/brewpi-test/bin:${PATH}" PYTHONDONTWRITEBYTECODE=1
WORKDIR /lab
CMD ["python3", "-u", "/work/tests/integration/run.py"]
