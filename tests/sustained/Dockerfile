# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
ARG BASE_IMAGE=brewpi-emulator-r4-build:arm64
FROM ${BASE_IMAGE}
RUN apt-get update && apt-get --download-only install -y --no-install-recommends git python3-venv python3-dev util-linux passwd && mkdir -p /opt/rmx-r3-inputs && sha256sum /var/cache/apt/archives/*.deb > /opt/rmx-r3-inputs/debs.sha256 && apt-get install -y --no-install-recommends git python3-venv python3-dev util-linux passwd && dpkg-query -W > /opt/rmx-r3-inputs/packages.tsv && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*.deb
COPY requirements.lock /opt/rmx-r3-inputs/requirements.lock
RUN python3 -m venv /opt/brewpi-test && /opt/brewpi-test/bin/pip install --disable-pip-version-check --require-hashes -r /opt/rmx-r3-inputs/requirements.lock && /opt/brewpi-test/bin/pip freeze > /opt/rmx-r3-inputs/python-packages.txt && groupadd -g 2001 brewpi && useradd -m -u 2001 -g 2001 brewpi && mkdir -p /lab /harness /source /refs /payload /evidence && chown 2001:2001 /lab /evidence
ENV PATH="/opt/brewpi-test/bin:${PATH}" PYTHONDONTWRITEBYTECODE=1 TZ=UTC LC_ALL=C HOME=/lab/home
WORKDIR /lab
USER 2001:2001
CMD ["python3","/harness/run.py"]
