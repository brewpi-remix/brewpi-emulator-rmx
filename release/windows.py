# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Build and verify unsigned native Windows ZIPs; never install a provider or publish."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import time
import zipfile

from artifacts import canonical, check_legal_provenance, command, safe_name, source_record, unpack, write_json
from version import application_version, checked_version
from runbook import render

ROOT = Path(__file__).resolve().parents[1]
DOC = 'share/doc/brewpi-emulator-rmx/'
FILES = {'bin/brewpi-emulator-rmx.exe': None,
         **{'libexec/brewpi-emulator-rmx/' + name: 'scripts/' + name
            for name in ['lcd-viewer.py', 'wait-ready.py', 'windows_channel.py', 'windows_ready.py']},
         DOC + 'LICENSE.md': 'LICENSE.md', DOC + 'THIRD_PARTY_NOTICES.md': 'THIRD_PARTY_NOTICES.md',
         DOC + 'operation.txt': 'docs/windows.txt',
         DOC + 'MSVC-STL-LICENSE.txt': 'release/notices/MSVC-STL-LICENSE.txt'}
LIMIT = 32 * 1024 * 1024
PROFILE = 'windows-amd64-local-controls-v1'
SYSTEM_IMPORTS = {'KERNEL32.DLL', 'ADVAPI32.DLL', 'BCRYPT.DLL', 'SETUPAPI.DLL', 'USER32.DLL',
                  'MSVCP140.DLL', 'VCRUNTIME140.DLL', 'VCRUNTIME140_1.DLL', 'UCRTBASE.DLL'}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def native(allow_server=False):
    if os.name != 'nt' or platform.machine().upper() != 'AMD64' or struct.calcsize('P') != 8:
        raise ValueError('native 64-bit Windows AMD64 Python is required')
    import ctypes
    from ctypes import wintypes as w
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.IsWow64Process2.argtypes = [w.HANDLE, ctypes.POINTER(w.USHORT), ctypes.POINTER(w.USHORT)]
    process, host = w.USHORT(), w.USHORT()
    if (not kernel.IsWow64Process2(kernel.GetCurrentProcess(), ctypes.byref(process), ctypes.byref(host))
            or process.value != 0 or host.value != 0x8664 or sys.getwindowsversion().build < 22000
            or (not allow_server and sys.getwindowsversion().product_type != 1)):
        raise ValueError('native Windows 11 x64 execution is required')
    if not __debug__:
        raise ValueError('Python assertions must be enabled')
    return dict(process_machine=process.value, native_machine=host.value,
                windows_build=sys.getwindowsversion().build, windows_product_type=sys.getwindowsversion().product_type)


def pe(binary):
    if not 256 <= Path(binary).stat().st_size <= LIMIT:
        raise ValueError('expected bounded PE executable')
    data = Path(binary).read_bytes()
    if not 256 <= len(data) <= LIMIT or data[:2] != b'MZ':
        raise ValueError('expected bounded PE executable')
    def number(offset, kind='<I'):
        size = struct.calcsize(kind)
        if offset < 0 or offset + size > len(data):
            raise ValueError('PE integer outside file')
        return struct.unpack_from(kind, data, offset)[0]
    offset = number(0x3c)
    if data[offset:offset + 4] != b'PE\0\0' or number(offset + 4, '<H') != 0x8664:
        raise ValueError('expected AMD64 PE executable')
    sections, optional = number(offset + 6, '<H'), offset + 24
    size = number(offset + 20, '<H')
    flags = number(offset + 22, '<H')
    if (not flags & 2 or flags & 0x2000 or size < 240 or number(optional, '<H') != 0x20b
            or number(optional + 68, '<H') != 3 or number(optional + 108) != 16):
        raise ValueError('invalid PE32+ console application headers')
    if number(optional + 112 + 4 * 8) or number(optional + 116 + 4 * 8):
        raise ValueError('Windows distribution must remain publisher-unsigned')
    if number(optional + 112 + 13 * 8) or number(optional + 116 + 13 * 8):
        raise ValueError('unreviewed delayed import closure')
    table = optional + size
    if not 1 <= sections <= 96 or table + sections * 40 > len(data):
        raise ValueError('invalid PE section table')
    def position(rva, length):
        for i in range(sections):
            row = table + i * 40
            address, raw_size, raw = [number(row + n) for n in [12, 16, 20]]
            if address <= rva and rva + length <= address + raw_size:
                at = raw + rva - address
                if at + length <= len(data):
                    return at
        raise ValueError('PE RVA outside bounded raw sections')
    rva, count = number(optional + 120), number(optional + 124)
    if not rva or count < 20 or count > 65536:
        raise ValueError('invalid PE import table')
    imports = []
    for index in range(count // 20):
        at = position(rva + index * 20, 20)
        row = data[at:at + 20]
        if row == bytes(20):
            break
        name_rva = number(at + 12)
        text = bytearray()
        for i in range(256):
            byte = data[position(name_rva + i, 1)]
            if not byte:
                break
            text.append(byte)
        else:
            raise ValueError('unbounded PE import name')
        name = text.decode('ascii').upper()
        if name not in SYSTEM_IMPORTS and not re.fullmatch(r'API-MS-WIN-CRT-[A-Z0-9-]+\.DLL', name):
            raise ValueError('unreviewed imported library: ' + name)
        if name in imports:
            raise ValueError('duplicate imported library')
        imports.append(name)
    else:
        raise ValueError('unterminated PE import table')
    if not imports:
        raise ValueError('empty PE dependency closure')
    return sorted(imports)


def inventory(tree):
    tree = Path(tree)
    if tree.is_symlink() or not tree.is_dir() or (hasattr(tree, 'is_junction') and tree.is_junction()):
        raise ValueError('Windows payload root is not an ordinary directory')
    rows = {}
    for path in tree.rglob('*'):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('reparse payload entry')
        if path.is_file():
            name = path.relative_to(tree).as_posix()
            safe_name(name)
            if path.stat().st_size > LIMIT:
                raise ValueError('oversized payload member')
            rows[name] = dict(sha256=sha(path), mode=0o755 if name.startswith(('bin/', 'libexec/')) else 0o644)
        elif not path.is_dir():
            raise ValueError('nonregular payload entry')
    if set(rows) != set(FILES):
        raise ValueError('Windows payload inventory differs')
    return rows


def archive(tree, path, top, rows, epoch):
    stamp = time.gmtime(max(315532800, epoch))[:6]
    with zipfile.ZipFile(path, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name, row in sorted(rows.items()):
            item = zipfile.ZipInfo(safe_name(top + '/' + name), stamp)
            item.create_system = 3
            item.external_attr = (0o100000 | row['mode']) << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            data = (Path(tree) / name).read_bytes()
            if len(data) > LIMIT or hashlib.sha256(data).hexdigest() != row['sha256']:
                raise ValueError('payload changed while archiving')
            output.writestr(item, data, compresslevel=9)


def verify_zip(path, top, rows):
    if Path(path).stat().st_size > LIMIT * len(FILES):
        raise ValueError('oversized Windows archive')
    with zipfile.ZipFile(path) as source:
        names = source.namelist()
        if len(names) != len(set(names)) or set(names) != {top + '/' + n for n in FILES}:
            raise ValueError('Windows archive inventory differs')
        for name, row in rows.items():
            member = source.getinfo(top + '/' + name)
            if (member.file_size > LIMIT or member.create_system != 3 or
                    member.external_attr >> 16 != 0o100000 | row['mode']):
                raise ValueError('Windows archive member metadata differs')
            digest, length = hashlib.sha256(), 0
            with source.open(member) as stream:
                for data in iter(lambda: stream.read(65536), b''):
                    length += len(data)
                    if length > LIMIT:
                        raise ValueError('expanded Windows member exceeds limit')
                    digest.update(data)
            if length != member.file_size or digest.hexdigest() != row['sha256']:
                raise ValueError('Windows archive member bytes differ')


def components(source, directory, output):
    headers, libraries, resources = {}, {}, {}
    tool_root = None
    sdk_root = Path(os.environ['ProgramFiles(x86)']) / 'Windows Kits/10'
    system = Path(os.environ['SystemRoot'])
    host_resources = {system / 'System32/TZRES.DLL', system / 'Globalization/Sorting/SORTDEFAULT.NLS'}
    for target in ['rmx_protocol.dir', 'rmx_lcd.dir', 'brewpi-emulator-rmx.dir']:
        logs = list((directory / target / 'Release').rglob('*.read.1.tlog'))
        if not logs:
            raise ValueError('missing native compiler/linker input records')
        for log in logs:
            if log.name not in ['CL.read.1.tlog', 'link.read.1.tlog', 'Lib-link.read.1.tlog']:
                continue
            for line in log.read_text(encoding='utf-16').splitlines():
                if not line or line.startswith('^'):
                    continue
                path = Path(line)
                if not path.is_absolute() or not path.is_file():
                    raise ValueError('unresolved compiler/linker input: ' + line)
                if source in path.parents or directory in path.parents:
                    continue
                if path in host_resources:
                    resources[str(path)] = sha(path)
                    continue
                parts = [x.lower() for x in path.parts]
                if 'msvc' in parts:
                    index = parts.index('msvc')
                    root = Path(*path.parts[:index + 2])
                    if tool_root is not None and root != tool_root:
                        raise ValueError('mixed MSVC toolset inputs')
                    tool_root = root
                elif sdk_root not in path.parents:
                    raise ValueError('unreviewed external compilation input: ' + line)
                table = headers if log.name == 'CL.read.1.tlog' else libraries
                table[str(path)] = sha(path)
    if not headers or not libraries or tool_root is None:
        raise ValueError('incomplete compiler/SDK component inventory')
    tools = {str(tool_root / ('bin/Hostx64/x64/' + name)):
             sha(tool_root / ('bin/Hostx64/x64/' + name)) for name in ['cl.exe', 'link.exe']}
    result = dict(original_license='MIT', producer='native-msbuild-input-records',
                  external_headers_sha256=headers, external_link_inputs_sha256=libraries,
                  external_host_locale_resources_sha256=resources,
                  tool_executables_sha256=tools, microsoft_sdk_root=str(sdk_root),
                  stl_license='Apache-2.0 WITH LLVM-exception',
                  stl_license_sha256=sha(source / 'release/notices/MSVC-STL-LICENSE.txt'),
                  runtime_dlls_bundled=False, provider_sdk_incorporated=False,
                  microsoft_proprietary_components='compiler startup/support and SDK retain Microsoft terms')
    write_json(output / 'component-inputs.json', result)
    return result


def build(source_archive, output, work, version):
    native()
    output, work = Path(output).resolve(), Path(work).resolve()
    output.mkdir(parents=True, exist_ok=False)
    work.mkdir(parents=True, exist_ok=False)
    roots, hashes = [], []
    record = None
    for label in ['first', 'second']:
        location = work / label
        source = unpack(source_archive, location / 'source', 'brewpi-emulator-rmx-' + version + '-source')
        current = source_record(source, version)
        if record is not None and current != record:
            raise ValueError('independent Windows source roots differ')
        record = current
        if (source / 'docs/windows.txt').read_text() != render(source, 'windows'):
            raise ValueError('standalone Windows guide is stale')
        directory = location / 'build'
        command(['cmake', '-S', source, '-B', directory, '-G', 'Visual Studio 18 2026', '-A', 'x64',
                 '-DCMAKE_INSTALL_PREFIX=' + str(location / 'install'),
                 '-DPython3_EXECUTABLE=' + sys.executable], output / (label + '-configure.log'))
        command(['cmake', '--build', directory, '--config', 'Release', '-j', '4'],
                output / (label + '-build.log'))
        binary = directory / 'Release/brewpi-emulator-rmx.exe'
        pe(binary)
        roots.append((source, directory, location / 'install'))
        hashes.append(sha(binary))
    if hashes[0] != hashes[1]:
        raise ValueError('complete independent-root Windows executable bytes differ')
    source, directory, tree = roots[0]
    components(source, directory, output)
    command(['ctest', '-C', 'Release', '--output-on-failure'], output / 'ctest.log', cwd=directory)
    command(['cmake', '--install', directory, '--config', 'Release'], output / 'install.log')
    command(['cmake', '--install', directory, '--config', 'Release', '--component', 'lcd-viewer'],
            output / 'viewer-install.log')
    rows = inventory(tree)
    for name, original in FILES.items():
        if original and rows[name]['sha256'] != record['files'][original]['sha256']:
            raise ValueError('installed original differs from source: ' + name)
    binary = tree / 'bin/brewpi-emulator-rmx.exe'
    if sha(binary) != hashes[0]:
        raise ValueError('installed executable differs from independently reproduced bytes')
    if subprocess.check_output([binary, '--version'], text=True, timeout=5).strip() != 'brewpi-emulator-rmx ' + version:
        raise ValueError('Windows application version differs')
    top = 'brewpi-emulator-rmx-' + version + '-windows-amd64'
    path = output / (top + '.zip')
    archive(tree, path, top, rows, record['source_date_epoch'])
    verify_zip(path, top, rows)
    shutil.copytree(tree, output / 'payload')
    write_json(output / 'source-record.json', record)
    result = dict(schema=4, profile=PROFILE, producer='local-native-build', version=version,
                  os='windows', architecture='amd64', minimum_windows='11', signature='unsigned',
                  acl_policy='inherit-private-extraction-directory; ZIP modes are not Windows ACLs',
                  source_commit=None, base_commit=record['base_commit'], identity_role=record['identity_role'],
                  source_snapshot_sha256=record['source_snapshot_sha256'], source_archive_sha256=sha(source_archive),
                  source_record_sha256=sha(output / 'source-record.json'), archive=path.name,
                  archive_sha256=sha(path), executable_sha256=hashes[0],
                  independently_reproduced_complete_bytes=True, imports=pe(binary), files=rows,
                  native_host=platform.platform(), qualification='pending',
                  external_prerequisites=['Microsoft Visual C++ v14 x64 runtime', 'approved external virtual COM pair',
                                          'optional Python/Tk; Python for readiness'],
                  component_inputs_sha256=sha(output / 'component-inputs.json'))
    write_json(output / 'windows-manifest.json', result)
    (output / 'SHA256SUMS').write_text(sha(path) + '  ' + path.name + '\n')
    return result


def verify(output, version, snapshot):
    output = Path(output).resolve(strict=True)
    manifest = json.loads((output / 'windows-manifest.json').read_text())
    if (manifest.get('schema') != 4 or manifest.get('profile') != PROFILE or
            manifest.get('version') != version or manifest.get('source_snapshot_sha256') != snapshot or
            manifest.get('os') != 'windows' or manifest.get('architecture') != 'amd64' or
            manifest.get('minimum_windows') != '11' or manifest.get('signature') != 'unsigned' or
            manifest.get('acl_policy') != 'inherit-private-extraction-directory; ZIP modes are not Windows ACLs' or
            manifest.get('source_commit') is not None or
            manifest.get('identity_role') != 'uncommitted-provisional-snapshot' or
            manifest.get('independently_reproduced_complete_bytes') is not True):
        raise ValueError('Windows manifest identity/profile differs')
    if sha(output / 'source-record.json') != manifest.get('source_record_sha256'):
        raise ValueError('Windows source record differs')
    if sha(output / 'component-inputs.json') != manifest.get('component_inputs_sha256'):
        raise ValueError('Windows component input inventory differs')
    components_record = json.loads((output / 'component-inputs.json').read_text())
    if (components_record.get('producer') != 'native-msbuild-input-records' or
            not components_record.get('external_headers_sha256') or
            not components_record.get('external_link_inputs_sha256') or
            components_record.get('runtime_dlls_bundled') is not False or
            components_record.get('provider_sdk_incorporated') is not False):
        raise ValueError('Windows compiler/SDK component record is incomplete')
    record = json.loads((output / 'source-record.json').read_text())
    content = {key: value for key, value in record.items() if key != 'source_snapshot_sha256'}
    if hashlib.sha256(canonical(content)).hexdigest() != snapshot:
        raise ValueError('Windows source metadata fingerprint differs')
    check_legal_provenance(record)
    if (record.get('source_snapshot_sha256') != snapshot or record.get('version') != version or
            record.get('base_commit') != manifest.get('base_commit')):
        raise ValueError('Windows source association differs')
    if components_record.get('stl_license_sha256') != record['files']['release/notices/MSVC-STL-LICENSE.txt']['sha256']:
        raise ValueError('Windows STL legal text binding differs')
    rows = inventory(output / 'payload')
    if rows != manifest['files']:
        raise ValueError('Windows payload differs')
    for name, original in FILES.items():
        if original and rows[name]['sha256'] != record['files'][original]['sha256']:
            raise ValueError('Windows original source binding differs')
    binary = output / 'payload/bin/brewpi-emulator-rmx.exe'
    if sha(binary) != manifest['executable_sha256'] or pe(binary) != manifest['imports']:
        raise ValueError('Windows executable/dependency identity differs')
    expected = 'brewpi-emulator-rmx-' + version + '-windows-amd64'
    if manifest['archive'] != expected + '.zip' or sha(output / manifest['archive']) != manifest['archive_sha256']:
        raise ValueError('Windows archive identity differs')
    verify_zip(output / manifest['archive'], expected, rows)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    b = sub.add_parser('build')
    b.add_argument('source', type=Path); b.add_argument('output', type=Path)
    b.add_argument('--work', type=Path, required=True)
    b.add_argument('--expected-version', default=application_version(ROOT))
    v = sub.add_parser('verify'); v.add_argument('output', type=Path)
    v.add_argument('--expected-version', default=application_version(ROOT))
    v.add_argument('--source-snapshot', required=True)
    args = parser.parse_args()
    version = checked_version(args.expected_version)
    result = (build(args.source, args.output, args.work, version) if args.action == 'build' else
              verify(args.output, version, args.source_snapshot))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
