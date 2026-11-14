# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
# External integration tools only; no reference sources enter this image.
FROM debian:bookworm-slim@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3
RUN apt-get update && apt-get install -y --no-install-recommends g++ cmake git python3-venv python3-dev php-cli php-mbstring chromium ca-certificates && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/brewpi-test
COPY requirements.txt /tmp/test-requirements.txt
RUN /opt/brewpi-test/bin/pip install --disable-pip-version-check -r /tmp/test-requirements.txt
RUN apt-get update && apt-get install -y --no-install-recommends make && rm -rf /var/lib/apt/lists/*
ENV PATH="/opt/brewpi-test/bin:${PATH}" PYTHONDONTWRITEBYTECODE=1
WORKDIR /lab
CMD ["python3", "-u", "/work/tests/integration/run.py"]
