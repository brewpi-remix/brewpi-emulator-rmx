# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Build and inspect source-associated native macOS archives; never publish."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

from artifacts import canonical, check_legal_provenance, command, safe_name, source_record, unpack, write_json
from runbook import render
from version import application_version, checked_version

ROOT = Path(__file__).resolve().parents[1]
DOC = 'share/doc/brewpi-emulator-rmx/'
FILES = {'bin/brewpi-emulator-rmx': None,
         'libexec/brewpi-emulator-rmx/wait-ready.py': 'scripts/wait-ready.py',
         'libexec/brewpi-emulator-rmx/lcd-viewer.py': 'scripts/lcd-viewer.py',
         DOC + 'LICENSE.md': 'LICENSE.md', DOC + 'THIRD_PARTY_NOTICES.md': 'THIRD_PARTY_NOTICES.md',
         DOC + 'operation.txt': 'docs/macos.txt', DOC + 'LLVM-LICENSE.txt': 'release/notices/LLVM-LICENSE.txt'}
LIBRARIES = ['/usr/lib/libc++.1.dylib', '/usr/lib/libSystem.B.dylib']
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def native():
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise ValueError('native macOS ARM64 execution is required')
    if int(platform.mac_ver()[0].split('.')[0]) < 27:
        raise ValueError('macOS 27 or later is required for this package profile')
    if not __debug__ or os.environ.get('PYTHONOPTIMIZE', '') not in ('', '0'):
        raise ValueError('Python assertions must be enabled')


def inventory(tree):
    tree = Path(tree)
    if tree.is_symlink() or not tree.is_dir():
        raise ValueError('payload root is not a regular directory')
    rows = {}
    for p in tree.rglob('*'):
        if p.is_symlink() or not (p.is_dir() or p.is_file()):
            raise ValueError('nonregular payload entry')
        if p.is_file():
            name = p.relative_to(tree).as_posix()
            safe_name(name)
            mode = stat.S_IMODE(p.stat().st_mode)
            expected = 0o755 if name.startswith(('bin/', 'libexec/')) else 0o644
            if mode != expected:
                raise ValueError('incorrect payload mode: ' + name)
            if p.stat().st_size > MAX_MEMBER_BYTES:
                raise ValueError('payload file exceeds native profile size limit')
            rows[name] = dict(sha256=sha(p), mode=mode)
    if set(rows) != set(FILES):
        raise ValueError('unexpected or missing macOS payload files')
    return rows


def macho(binary):
    data = Path(binary).read_bytes()
    if len(data) < 32 or data[:4] != b'\xcf\xfa\xed\xfe' or int.from_bytes(data[4:8], 'little') != 0x100000c:
        raise ValueError('expected thin ARM64 Mach-O executable')
    if int.from_bytes(data[12:16], 'little') != 2:
        raise ValueError('Mach-O input is not an executable')
    count, size = [int.from_bytes(data[i:i + 4], 'little') for i in [16, 20]]
    if size > len(data) - 32 or count > size // 8:
        raise ValueError('invalid Mach-O load-command bounds')
    position, versions = 32, []
    for _ in range(count):
        if position + 8 > 32 + size:
            raise ValueError('truncated Mach-O load command')
        kind = int.from_bytes(data[position:position + 4], 'little')
        length = int.from_bytes(data[position + 4:position + 8], 'little')
        if length < 8 or length % 8 or position + length > 32 + size:
            raise ValueError('invalid Mach-O load-command length')
        if kind == 0x32:
            if length < 24:
                raise ValueError('truncated Mach-O build-version command')
            versions.append((int.from_bytes(data[position + 8:position + 12], 'little'),
                             int.from_bytes(data[position + 12:position + 16], 'little')))
        position += length
    if position != 32 + size or versions != [(1, 27 << 16)]:
        raise ValueError('Mach-O platform/minimum OS differs from macOS 27.0 profile')
    return data


def pack(tree, archive, top, epoch):
    rows = inventory(tree)
    stamp = time.gmtime(max(315532800, epoch))[:6]
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name, row in sorted(rows.items()):
            info = zipfile.ZipInfo(safe_name(top + '/' + name), stamp)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | row['mode']) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with (Path(tree) / name).open('rb') as stream:
                data = stream.read(MAX_MEMBER_BYTES + 1)
            if len(data) > MAX_MEMBER_BYTES or hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError('payload changed while creating archive')
            output.writestr(info, data, compresslevel=9)
    return rows


def verify_archive(archive, top, rows):
    if Path(archive).stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError('archive exceeds native profile size limit')
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        if len(names) != len(set(names)) or set(names) != {top + '/' + n for n in FILES}:
            raise ValueError('archive inventory differs')
        for name, row in rows.items():
            info = source.getinfo(safe_name(top + '/' + name))
            if info.create_system != 3 or info.external_attr >> 16 != stat.S_IFREG | row['mode']:
                raise ValueError('archive entry type/mode differs')
            if info.file_size > MAX_MEMBER_BYTES:
                raise ValueError('archive member exceeds native profile size limit')
            digest, length = hashlib.sha256(), 0
            with source.open(info) as stream:
                for block in iter(lambda: stream.read(65536), b''):
                    length += len(block)
                    if length > MAX_MEMBER_BYTES:
                        raise ValueError('archive member expanded beyond native profile size limit')
                    digest.update(block)
            if length != info.file_size or digest.hexdigest() != row['sha256']:
                raise ValueError('archive bytes differ')


def build(source_archive, output, work, identity, team, expected_version):
    native()
    if not re.fullmatch('[0-9A-Fa-f]{40}', identity) or not re.fullmatch('[A-Z0-9]{10}', team):
        raise ValueError('explicit certificate fingerprint and team are required')
    output, work = Path(output).resolve(), Path(work).resolve()
    output.mkdir(parents=True, exist_ok=False)
    work.mkdir(parents=True, exist_ok=False)
    top = 'brewpi-emulator-rmx-' + expected_version
    # Preserve the C++ driver name: resolving clang++ to clang changes linking.
    compiler = Path(subprocess.check_output(['xcrun', '--find', 'clang++'], text=True).strip()).absolute()
    sdk = Path(subprocess.check_output(['xcrun', '--show-sdk-path'], text=True).strip()).resolve()
    roots, hashes = [], []
    record = None
    for label in ['first', 'second']:
        location = work / label
        source = unpack(source_archive, location / 'source', top + '-source')
        current = source_record(source, expected_version)
        if record is not None and record != current:
            raise ValueError('independent roots have different source records')
        record = current
        if (source / 'docs/macos.txt').read_text() != render(source, 'macos'):
            raise ValueError('standalone macOS guide is stale')
        directory = location / 'build'
        command(['cmake', '-S', source, '-B', directory, '-DCMAKE_BUILD_TYPE=Release',
                 '-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_OSX_DEPLOYMENT_TARGET=27.0',
                 '-DCMAKE_CXX_COMPILER=' + str(compiler), '-DCMAKE_OSX_SYSROOT=' + str(sdk),
                 '-DCMAKE_INSTALL_PREFIX=/usr/local'], output / (label + '-configure.log'))
        command(['cmake', '--build', directory, '-j2'], output / (label + '-build.log'))
        binary = directory / 'brewpi-emulator-rmx'
        macho(binary)
        hashes.append(sha(binary))
        roots.append((source, directory))
    if hashes[0] != hashes[1]:
        raise ValueError('independent pre-publisher-signing Mach-O builds differ')
    source, directory = roots[0]
    link = shlex.split((directory / 'CMakeFiles/brewpi-emulator-rmx.dir/link.txt').read_text())
    command(link + ['-Wl,-map,' + str(output / 'link-map.txt')], output / 'audit-link.log', cwd=directory)
    if sha(directory / 'brewpi-emulator-rmx') != hashes[0]:
        raise ValueError('diagnostic link-map generation changed executable bytes')
    headers = {}
    for target in ['rmx_protocol.dir', 'rmx_lcd.dir', 'brewpi-emulator-rmx.dir']:
        for dependency in (directory / 'CMakeFiles' / target).rglob('*.o.d'):
            for name in shlex.split(dependency.read_text().replace('\\\n', ' '))[1:]:
                path = Path(name)
                if not path.is_absolute() or not path.is_file() or source in path.parents:
                    continue
                if sdk not in path.parents and compiler.parent.parent not in path.parents:
                    raise ValueError('unreviewed external compilation input: ' + name)
                headers[str(path)] = sha(path)
    if not headers:
        raise ValueError('no compiler/SDK header inventory found')
    write_json(output / 'component-inputs.json', dict(original_license='MIT', external_header_sha256=headers,
                                                    compiler=str(compiler), compiler_sha256=sha(compiler),
                                                    llvm_license_sha256=record['files']['release/notices/LLVM-LICENSE.txt']['sha256'],
                                                    link_map_sha256=sha(output / 'link-map.txt'), review_required=True))
    command(['ctest', '--output-on-failure'], output / 'ctest.log', cwd=directory)
    staged = work / 'stage'
    env = dict(os.environ, DESTDIR=str(staged))
    command(['cmake', '--install', directory], output / 'install.log', env=env)
    command(['cmake', '--install', directory, '--component', 'lcd-viewer'], output / 'viewer-install.log', env=env)
    tree = staged / 'usr/local'
    unsigned = inventory(tree)
    for name, original in FILES.items():
        if original and unsigned[name]['sha256'] != record['files'][original]['sha256']:
            raise ValueError('installed original input differs: ' + name)
    binary = tree / 'bin/brewpi-emulator-rmx'
    dependencies = subprocess.check_output(['otool', '-L', binary], text=True)
    libraries = [line.strip().split(' (')[0] for line in dependencies.splitlines()[1:]]
    if libraries != LIBRARIES:
        raise ValueError('unreviewed runtime dependency closure: ' + repr(libraries))
    command(['codesign', '--force', '--sign', identity, '--options', 'runtime', '--timestamp', binary], output / 'sign.log')
    command(['codesign', '--verify', '--strict', '--verbose=2', binary], output / 'signature-verify.log')
    signature = subprocess.run(['codesign', '-d', '--verbose=4', binary], capture_output=True, text=True, check=True).stderr
    if 'TeamIdentifier=' + team not in signature or 'Authority=Developer ID Application:' not in signature:
        raise ValueError('signed output does not match the approved Developer ID team')
    version = subprocess.check_output([binary, '--version'], text=True, timeout=5).strip()
    if version != 'brewpi-emulator-rmx ' + expected_version:
        raise ValueError('signed application version differs')
    name = top + '-macos-arm64'
    archive = output / (name + '.zip')
    rows = pack(tree, archive, name, record['source_date_epoch'])
    verify_archive(archive, name, rows)
    shutil.copytree(tree, output / 'payload')
    write_json(output / 'source-record.json', record)
    manifest = dict(schema=4, producer='local-native-build', profile='macos-arm64-local-controls-v2',
                    version=expected_version, os='macos', architecture='arm64', minimum_macos='27.0',
                    source_commit=None, base_commit=record['base_commit'],
                    source_snapshot_sha256=record['source_snapshot_sha256'], source_archive_sha256=sha(source_archive),
                    identity_role='uncommitted-provisional-snapshot', archive=archive.name, archive_sha256=sha(archive),
                    pre_publisher_signing_sha256=hashes[0], independently_reproduced_pre_signing_bytes=True,
                    publisher_signatures_reproducible=False, signature_team=team, certificate_fingerprint=identity.upper(),
                    signature_details=signature, libraries=libraries, files=rows,
                    compiler=subprocess.check_output([compiler, '--version'], text=True).splitlines()[0],
                    compiler_sha256=sha(compiler), sdk_path=str(sdk),
                    sdk=subprocess.check_output(['xcrun', '--show-sdk-version'], text=True).strip(),
                    native_host=platform.platform(), notarization='pending', qualification='pending')
    manifest['component_inputs_sha256'] = sha(output / 'component-inputs.json')
    manifest['source_record_sha256'] = sha(output / 'source-record.json')
    write_json(output / 'macos-manifest.json', manifest)
    (output / 'SHA256SUMS').write_text(sha(archive) + '  ' + archive.name + '\n')
    return manifest


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate manifest key: ' + key)
        result[key] = value
    return result


def verify(output, expected_version=None, expected_snapshot=None):
    native()
    output = Path(output).resolve()
    manifest = json.loads((output / 'macos-manifest.json').read_text(), object_pairs_hook=unique)
    if manifest.get('schema') != 4 or manifest.get('profile') != 'macos-arm64-local-controls-v2' or manifest.get('producer') != 'local-native-build' or manifest.get('os') != 'macos' or manifest.get('architecture') != 'arm64':
        raise ValueError('unsupported native manifest profile')
    expected_version = checked_version(expected_version or application_version(ROOT))
    if manifest.get('version') != expected_version:
        raise ValueError('saved package version differs from explicit expectation')
    if manifest.get('source_commit') is not None or manifest.get('identity_role') != 'uncommitted-provisional-snapshot':
        raise ValueError('incorrect uncommitted source identity')
    for field, length in [('base_commit', 40), ('source_snapshot_sha256', 64), ('source_archive_sha256', 64)]:
        if not re.fullmatch('[0-9a-f]{' + str(length) + '}', manifest.get(field, '')):
            raise ValueError('invalid source association: ' + field)
    if not isinstance(expected_snapshot, str) or manifest['source_snapshot_sha256'] != expected_snapshot:
        raise ValueError('explicit expected source snapshot is required and must match')
    if sha(output / 'source-record.json') != manifest.get('source_record_sha256'):
        raise ValueError('source record changed')
    record = json.loads((output / 'source-record.json').read_text(), object_pairs_hook=unique)
    if type(record.get('schema')) is not int or record['schema'] != 1 or record.get('spdx_license_identifier') != 'MIT' or record.get('identity_role') != 'uncommitted-provisional-snapshot':
        raise ValueError('unsupported source-record policy')
    check_legal_provenance(record)
    content = {key: value for key, value in record.items() if key != 'source_snapshot_sha256'}
    if hashlib.sha256(canonical(content)).hexdigest() != expected_snapshot or record.get('source_snapshot_sha256') != expected_snapshot or record.get('version') != expected_version or record.get('base_commit') != manifest['base_commit'] or record.get('source_commit') is not None:
        raise ValueError('source record does not match the expected snapshot')
    if set(manifest.get('files', {})) != set(FILES):
        raise ValueError('incomplete native payload inventory')
    for name, original in FILES.items():
        if original and manifest['files'][name]['sha256'] != record['files'][original]['sha256']:
            raise ValueError('original payload file does not match source: ' + name)
    if manifest.get('libraries') != LIBRARIES or manifest.get('minimum_macos') != '27.0':
        raise ValueError('unsupported native dependency/OS profile')
    if sha(output / 'component-inputs.json') != manifest.get('component_inputs_sha256'):
        raise ValueError('component inventory changed')
    archive = output / safe_name(manifest['archive'])
    if archive.parent != output or sha(archive) != manifest['archive_sha256']:
        raise ValueError('archive identity differs')
    top = 'brewpi-emulator-rmx-' + checked_version(manifest['version']) + '-macos-arm64'
    if inventory(output / 'payload') != manifest['files']:
        raise ValueError('retained payload differs')
    verify_archive(archive, top, manifest['files'])
    binary = output / 'payload/bin/brewpi-emulator-rmx'
    macho(binary)
    subprocess.run(['codesign', '--verify', '--strict', binary], check=True)
    signature = subprocess.run(['codesign', '-d', '--verbose=4', binary], capture_output=True, text=True, check=True).stderr
    if not re.fullmatch('[A-Z0-9]{10}', manifest.get('signature_team', '')) or 'TeamIdentifier=' + manifest['signature_team'] not in signature or 'Authority=Developer ID Application:' not in signature:
        raise ValueError('Developer ID signature team differs')
    with tempfile.TemporaryDirectory(prefix='rmx-public-signing-cert-') as tmp:
        prefix = str(Path(tmp) / 'certificate')
        subprocess.run(['codesign', '-d', '--extract-certificates=' + prefix, binary], capture_output=True, check=True)
        fingerprint = subprocess.check_output(['openssl', 'x509', '-inform', 'DER', '-in', prefix + '0',
                                              '-noout', '-fingerprint', '-sha1'], text=True).strip().split('=')[-1].replace(':', '')
        if fingerprint != manifest.get('certificate_fingerprint'):
            raise ValueError('Developer ID leaf certificate differs')
    if subprocess.check_output([binary, '--version'], text=True, timeout=5).strip() != 'brewpi-emulator-rmx ' + expected_version:
        raise ValueError('signed executable version differs')
    return manifest


def notarize(output, profile, expected_version=None, expected_snapshot=None):
    manifest = verify(output, expected_version, expected_snapshot)
    output = Path(output).resolve()
    receipt = output / 'notarization-submission.json'
    if receipt.exists() or (output / 'notarization-request.json').exists():
        raise ValueError('submission already exists; inspect its retained ID rather than resubmitting')
    # Authenticate before reserving an upload attempt. Do not retain or print
    # unrelated account history. Once upload begins, an ambiguous failure must
    # still leave the request marker so it cannot cause a blind resubmission.
    subprocess.run(['xcrun', 'notarytool', 'history', '--keychain-profile', profile,
                    '--output-format', 'json'], stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE, check=True, text=True, timeout=30)
    write_json(output / 'notarization-request.json', dict(archive_sha256=manifest['archive_sha256'],
                                                        manifest_sha256=sha(output / 'macos-manifest.json')))
    result = subprocess.check_output(['xcrun', 'notarytool', 'submit', output / manifest['archive'],
                                      '--keychain-profile', profile, '--output-format', 'json'], text=True, timeout=120)
    value = json.loads(result)
    if str(uuid.UUID(value.get('id', ''))) != value['id']:
        raise ValueError('notary service did not return a submission ID')
    write_json(receipt, dict(producer='apple-notary-service', submission=value,
                            archive_sha256=manifest['archive_sha256'], manifest_sha256=sha(output / 'macos-manifest.json')))
    return value


def notarization_status(output, profile, expected_version=None, expected_snapshot=None):
    manifest = verify(output, expected_version, expected_snapshot)
    output = Path(output).resolve()
    receipt = json.loads((output / 'notarization-submission.json').read_text(), object_pairs_hook=unique)
    if receipt.get('archive_sha256') != manifest['archive_sha256'] or receipt.get('manifest_sha256') != sha(output / 'macos-manifest.json'):
        raise ValueError('submission does not identify the retained package')
    identifier = str(uuid.UUID(receipt['submission']['id']))
    result = subprocess.check_output(['xcrun', 'notarytool', 'info', identifier, '--keychain-profile', profile,
                                      '--output-format', 'json'], text=True, timeout=30)
    value = json.loads(result, object_pairs_hook=unique)
    if value.get('id') != identifier:
        raise ValueError('notary service returned a different submission identity')
    record = dict(producer='apple-notary-service', archive_sha256=manifest['archive_sha256'],
                  manifest_sha256=receipt['manifest_sha256'], response=value,
                  native_package_qualification='separate gate, not established by notarization')
    for attempt in range(1, 101):
        path = output / ('notarization-status-' + str(attempt) + '.json')
        if not path.exists():
            write_json(path, record)
            return record
    raise ValueError('retain/review existing status evidence before requesting further checks')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    b = sub.add_parser('build')
    b.add_argument('source'); b.add_argument('output'); b.add_argument('--work', required=True)
    b.add_argument('--identity', required=True); b.add_argument('--team', required=True)
    b.add_argument('--expected-version', default=application_version(ROOT))
    v = sub.add_parser('verify'); v.add_argument('output'); v.add_argument('--expected-version')
    v.add_argument('--source-snapshot', required=True)
    n = sub.add_parser('notarize'); n.add_argument('output'); n.add_argument('--profile', required=True)
    n.add_argument('--expected-version')
    n.add_argument('--source-snapshot', required=True)
    s = sub.add_parser('status'); s.add_argument('output'); s.add_argument('--profile', required=True)
    s.add_argument('--expected-version')
    s.add_argument('--source-snapshot', required=True)
    args = parser.parse_args()
    if args.action == 'build':
        value = build(args.source, args.output, args.work, args.identity, args.team, checked_version(args.expected_version))
    elif args.action == 'verify':
        value = verify(args.output, args.expected_version, args.source_snapshot)
    elif args.action == 'notarize':
        value = notarize(args.output, args.profile, args.expected_version, args.source_snapshot)
    else:
        value = notarization_status(args.output, args.profile, args.expected_version, args.source_snapshot)
    print(json.dumps(value, indent=2))


if __name__ == '__main__':
    main()
