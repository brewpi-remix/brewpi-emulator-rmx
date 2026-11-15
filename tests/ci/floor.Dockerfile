# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
# Build external minimum-version tools from hashed official source inputs.
ARG BASE=brewpi-emulator-ci:r2
FROM ${BASE}
RUN apt-get update && apt-get install -y --no-install-recommends curl libssl-dev zlib1g-dev libffi-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /tmp/floors
RUN curl --fail --location https://github.com/Kitware/CMake/releases/download/v3.16.9/cmake-3.16.9.tar.gz -o cmake.tar.gz && echo '1708361827a5a0de37d55f5c9698004c035abb1de6120a376d5d59a81630191f  cmake.tar.gz' | sha256sum -c - && tar xf cmake.tar.gz && cmake -S cmake-3.16.9 -B cmake-build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/floor-cmake -DCMAKE_USE_OPENSSL=OFF && cmake --build cmake-build -j4 && cmake --install cmake-build
RUN curl --fail --location https://www.python.org/ftp/python/3.9.25/Python-3.9.25.tar.xz -o python.tar.xz && echo '00e07d7c0f2f0cc002432d1ee84d2a40dae404a99303e3f97701c10966c91834  python.tar.xz' | sha256sum -c - && python3 -c "import tarfile; tarfile.open('python.tar.xz').extractall('.')" && cd Python-3.9.25 && ./configure --prefix=/opt/floor-python --without-ensurepip && make -j4 && make install
WORKDIR /work
