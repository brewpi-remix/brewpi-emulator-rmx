# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Provision the external pinned workflow linter; retain no upstream code in Git."""
import hashlib
from pathlib import Path
import subprocess
import tarfile
import tempfile
import urllib.request
from payload import preflight

VERSION='1.7.7'
SHA256='023070a287cd8cccd71515fedc843f1985bf96c436b7effaecce67290e7e0757'


def main():
    preflight()
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        with urllib.request.urlopen('https://github.com/rhysd/actionlint/releases/download/v'+VERSION+'/actionlint_'+VERSION+'_linux_amd64.tar.gz',timeout=30) as response:
            data=response.read()
        if hashlib.sha256(data).hexdigest()!=SHA256:raise ValueError('actionlint input hash differs')
        archive=root/'input.tar.gz';archive.write_bytes(data)
        with tarfile.open(archive) as source:
            tool=root/'actionlint';tool.write_bytes(source.extractfile('actionlint').read());tool.chmod(0o700)
        subprocess.run([str(tool),'-shellcheck=','-pyflakes=',*[str(p) for p in sorted((Path(__file__).resolve().parents[2]/'.github/workflows').glob('*.yml'))]],check=True)


if __name__=='__main__':main()
