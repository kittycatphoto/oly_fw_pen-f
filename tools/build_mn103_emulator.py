#!/usr/bin/env python3
# Copyright 2026 fishku (original contributions)
# SPDX-License-Identifier: Apache-2.0
# Scope and third-party exceptions: see RIGHTS-AND-PROVENANCE.md.
"""Build the pinned GNU MN103 core and offline harness locally (no network).

For a fresh checkout, supply --archive with the upstream tar.gz named in
EMULATOR.md. Subsequent builds reuse the source tree and build dependencies.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'toolchains/mn103-gnu-src'
BUILD = ROOT / 'toolchains/mn103-gnu-build'
REVISION = '87ffb882e0f4d73401a0746177ffabb8e8bbe4ac'
ARCHIVE_SHA256 = 'a5e7cd02f844bb2873c25e0ac8e9a5b50a72c3e8e6570a6b7821d2e4c21178ad'
# googlesource regenerates the tar.gz (and the tar's timestamps) on every download, so a fresh copy never has
# ARCHIVE_SHA256. Its files are still the commit's: the git tree hash rebuilt from the archive members must equal
# the pinned commit's tree (upstream `git rev-parse 87ffb882^{tree}`).
TREE = '059d50a3cc76bd13dc10f21023863674e6da515c'
CONFIGURE = ['--target=mn10300-elf', '--disable-gdb', '--disable-gdbserver',
             '--disable-binutils', '--disable-gas', '--disable-ld', '--disable-gprof',
             '--disable-gprofng', '--disable-nls', '--disable-werror',
             '--without-debuginfod', '--enable-sim', '--disable-sim-hardware']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive_tree(path):
    """Git tree hash of a tar archive's files (modes 100644 / 100755 / 120000), computed without git."""
    root = {}
    with tarfile.open(path) as archive:
        for member in archive:
            if member.isdir():
                continue
            if not (member.isfile() or member.issym()):
                raise ValueError(f'Unexpected archive member type: {member.name}')
            name = member.name[2:] if member.name.startswith('./') else member.name
            if member.issym():
                data, mode = member.linkname.encode(), b'120000'
            else:
                data = archive.extractfile(member).read()
                mode = b'100755' if member.mode & 0o111 else b'100644'
            node = root
            *dirs, leaf = name.split('/')
            for part in dirs:
                node = node.setdefault(part, {})
            node[leaf] = (mode, hashlib.sha1(b'blob %d\0' % len(data) + data).digest())

    def tree(node):
        entries = []
        for name, value in node.items():
            if isinstance(value, dict):
                entries.append((name + '/', b'40000', name, tree(value)))
            else:
                entries.append((name, value[0], name, value[1]))
        body = b''.join(mode + b' ' + name.encode() + b'\0' + digest
                        for _, mode, name, digest in sorted(entries, key=lambda e: e[0].encode()))
        return hashlib.sha1(b'tree %d\0' % len(body) + body).digest()

    return tree(root).hex()


def run(args, log, cwd=BUILD):
    print('Running:', ' '.join(map(str, args)), flush=True)
    with log.open('w') as out:
        proc = subprocess.run(args, cwd=cwd, stdout=out, stderr=subprocess.STDOUT)
    if proc.returncode:
        print('\n'.join(log.read_text(errors='replace').splitlines()[-35:]))
        raise SystemExit(f'Build failed; see {log}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path)
    p.add_argument('--jobs', type=int, default=4)
    args = p.parse_args()
    if not (SRC / '.penf-source.json').is_file():
        if not args.archive:
            p.error('A fresh build requires the pinned upstream archive (--archive)')
        archive_sha = sha(args.archive)
        if archive_sha == ARCHIVE_SHA256:
            verified = 'archive_sha256'
        elif archive_tree(args.archive) == TREE:
            verified = 'git_tree'
        else:
            p.error('Archive is neither the pinned file nor the pinned commit tree')
        SRC.mkdir(parents=True, exist_ok=True)
        with tarfile.open(args.archive) as archive:
            archive.extractall(SRC, filter='data')
        (SRC / '.penf-source.json').write_text(json.dumps(
            {'revision': REVISION, 'tree': TREE, 'archive_sha256': archive_sha, 'verified_by': verified}, indent=2)+'\n')
    source = json.loads((SRC / '.penf-source.json').read_text())
    if source['revision'] != REVISION or not (source['archive_sha256'] == ARCHIVE_SHA256
                                              or source.get('tree') == TREE):
        p.error('Unexpected source provenance')
    subprocess.run([sys.executable, str(ROOT / 'tools/prepare_mn103_sim.py')], check=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    if not (BUILD / 'Makefile').is_file():
        run([str(SRC / 'configure'), *CONFIGURE], BUILD / 'configure.log')
    run(['make', f'-j{args.jobs}', 'all-sim', 'MAKEINFO=true'], BUILD / 'build.log')
    # Reuse exactly the simulator's include paths and dependency/link settings.
    makefile = BUILD / 'sim/penf-harness.mk'
    makefile.write_text('''mn10300/penf_runner.o: ../../../tools/mn103_runner.c
\t$(COMPILE) -c -o $@ $<

../penf-mn103: mn10300/penf_runner.o mn10300/libsim.a $(SIM_COMMON_LIBS)
\t$(LINK) mn10300/penf_runner.o mn10300/libsim.a $(SIM_COMMON_LIBS) $(LIBS)
''')
    run(['make', '-f', 'Makefile', '-f', makefile.name, '../penf-mn103', 'V=1'],
        BUILD / 'harness-build.log', BUILD / 'sim')
    files = ['tools/mn103_runner.c', 'tools/prepare_mn103_sim.py', 'tools/mn103_strict.patch',
             'toolchains/mn103-gnu-src/sim/mn10300/interp.c',
             'toolchains/mn103-gnu-src/sim/mn10300/mn10300.igen',
             'toolchains/mn103-gnu-build/penf-mn103']
    (BUILD / 'penf-build.json').write_text(json.dumps({'upstream': source, 'configure': CONFIGURE,
                                                    'sha256': {p: sha(ROOT / p) for p in files}}, indent=2)+'\n')
    print('Built:', BUILD / 'penf-mn103')


if __name__ == '__main__':
    main()
