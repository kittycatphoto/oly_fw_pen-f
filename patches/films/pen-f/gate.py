#!/usr/bin/env python3
# Copyright 2026 kittycatphoto (original contributions)
# SPDX-License-Identifier: Apache-2.0
"""Startup-safety gate for a PEN-F films package (research/penf_caduceus/08_STARTUP_SAFETY.md).

Static checks on the decoded main of a built package against the HSL base it was built on:
 1. Placement: every changed byte lies in the boot part or in a section loaded before the GUI starts (1-5), and
    none of them fills a 0xFF gap (free space that is not shown to be loaded).
 2. Reachability of the films region (the reclaimed osd handler, 0x60a79cdc..0x60a7b434): every reference into it
    that is new in the package -- a 32-bit word at any offset, or a pc-relative call / jmp / calls at any offset --
    comes from a declared redirect range of the spec or from the films block itself. References the base already
    had are listed for review: they must target the stubbed handler entry or be bytes inside other instructions.
 3. The handler entry is stubbed (clr d0; rets), so the debug shell cannot run the region's new contents.
 4. Every hook (assemble.REDIRECTS) decodes, from the package's own bytes, to exactly its function in this build's
    films.elf. (v1.2-r1 shipped v1.1's hook bytes after the functions had moved: a boot loop the rest missed.)

  python3 gate.py --package generated/films-v1.2/install/DCOLYMP/E1229999.BIN \
                  --base generated/films-v1.2/base-hsl/install/DCOLYMP/E1229999.BIN --spec generated/patch-v1.2.json \
                  --elf generated/asm-v12/films.elf

A raw scanner over-reports (bytes inside other instructions can look like a branch); it never under-reports the
encodings it knows. PASS is static evidence only: it does not run the constructors or boot.
"""
import argparse
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'tools'))
from oly_container import parse  # noqa: E402
sys.path.insert(0, str(HERE))
import assemble  # noqa: E402

BASE = 0x60021020
BOOT = (0x60021020, 0x60142800)
DATA_INIT = (0x601ea800, 0x6020b220)     # .data initializer image, copied to RAM at boot (AF Limiter menu row)
EARLY = [(0x60142800, 0x601cb000), (0x6022a800, 0x60428000), (0x60432800, 0x6069b800),
         (0x606b4800, 0x60a50000), (0x60a76000, 0x60fdc800)]       # sections 1-5 (startup audit)
REGION = (0x60a79cdc, 0x60a7b434)
HANDLER_ENTRY = 0x60a79cd6
DEAD = (HANDLER_ENTRY, 0x60a7b435)       # the whole osd handler: unreachable once its entry is stubbed (07_RECLAIM)
# Base references into the region that are bytes inside other instructions (checked by disassembly, 2026-11-25).
REVIEWED = {
    **{a: 'immediate of mov 0x1700100X,d0 (fc cc ..)' for a in
       (0x60a79b63, 0x60a79b86, 0x60a79bc6, 0x60a79bea, 0x60a79c19, 0x60a79c4b, 0x60a79c6f, 0x60a79c9d)},
    0x60a7bea5: 'frame byte of call 0x60a7ba71,[d2,d3,a2],12 at 0x60a7bea4',
    0x60a8218f: 'address bytes of movbu d0,(0x618f50cc)',
    0x60a8219e: 'inside an instruction of the same function as 0x60a8218f',
    0x60a821f2: 'immediate of mov 0x6191f4cc,a1 (fc dd cc ..)',
    0x60a82f2f: 'frame byte of call 0x60a830fa,[d2],12 at 0x60a82f2e',
    0x60b7800e: 'immediate of mov 0x6160a7ac,a0 (fc dc ac a7 60 61), read one byte in',
}
STUB = bytes.fromhex('00f0fc')                                       # clr d0; rets


def main_of(path):
    blocks = parse(Path(path).read_bytes())
    return blocks[0].payload


def inside(addr, ranges):
    return any(lo <= addr < hi for lo, hi in ranges)


def references(data, lo, hi):
    """(source address, kind, target, length) for every encoding at any offset whose target is in [lo, hi)."""
    out = []
    n = len(data)
    for i in range(n - 3):
        word = struct.unpack_from('<I', data, i)[0]
        if lo <= word < hi:
            out.append((BASE + i, 'word', word, 4))
    for i in range(n - 5):
        op = data[i]
        if op in (0xdc, 0xdd):                                       # jmp / call (d32, pc-relative)
            target = (BASE + i + struct.unpack_from('<i', data, i + 1)[0]) & 0xffffffff
            if lo <= target < hi:
                out.append((BASE + i, 'jmp32' if op == 0xdc else 'call32', target, 5))
        elif op in (0xcc, 0xcd):                                     # jmp / call (d16)
            target = (BASE + i + struct.unpack_from('<h', data, i + 1)[0]) & 0xffffffff
            if lo <= target < hi:
                out.append((BASE + i, 'jmp16' if op == 0xcc else 'call16', target, 3))
        elif op == 0xfc and data[i + 1] == 0xff:                     # calls (d32)
            target = (BASE + i + struct.unpack_from('<i', data, i + 2)[0]) & 0xffffffff
            if lo <= target < hi:
                out.append((BASE + i, 'calls32', target, 6))
        elif op == 0xfa and data[i + 1] == 0xff:                     # calls (d16)
            target = (BASE + i + struct.unpack_from('<h', data, i + 2)[0]) & 0xffffffff
            if lo <= target < hi:
                out.append((BASE + i, 'calls16', target, 4))
    return out


def gate(package, base, spec, sym=None):
    new, old = main_of(package), main_of(base)
    if len(new) != len(old):
        raise ValueError('main sizes differ')
    ranges = [(int(r['address'], 16), int(r['address'], 16) + r['bytes']) for r in spec['main_ranges']]
    films_block = next((lo, hi) for lo, hi in ranges if lo == REGION[0] + 4)
    report = {'checks': []}

    def check(name, ok, **detail):
        report['checks'].append({'check': name, 'pass': bool(ok), **detail})

    changed = [BASE + i for i in range(len(new)) if new[i] != old[i]]
    outside = [a for a in changed if not inside(a, [BOOT, DATA_INIT] + EARLY)]
    undeclared = [a for a in changed if not inside(a, ranges)]
    check('placement: changed bytes are in the boot part, its .data image or sections 1-5', not outside,
          changed_bytes=len(changed), outside=[hex(a) for a in outside[:10]])
    check('placement: every changed byte is in a declared spec range', not undeclared,
          undeclared=[hex(a) for a in undeclared[:10]])
    check('handler entry stubbed (clr d0; rets)', new[HANDLER_ENTRY - BASE:HANDLER_ENTRY - BASE + 3] == STUB)

    def overlaps(ref, spans):
        return any(ref[0] < hi and lo < ref[0] + ref[3] for lo, hi in spans)

    refs_new = set(references(new, *REGION))
    refs_old = set(references(old, *REGION))
    added = sorted(refs_new - refs_old)
    redirect_ranges = [r for r in ranges if r != films_block]
    from_redirects = [r for r in added if overlaps(r, redirect_ranges)]
    from_block = [r for r in added if inside(r[0], [films_block])]
    stray = [r for r in added if r not in from_redirects and r not in from_block]
    check('reachability: new references into the films region come from declared redirects or the block itself',
          not stray, redirects=sorted({hex(r[0]) for r in from_redirects}), from_block=len(from_block),
          stray=[(hex(a), k, hex(t)) for a, k, t, _ in stray[:20]])
    early = [r for r in from_redirects if not inside(r[0], EARLY + [BOOT])]
    check('reachability: every redirect site is itself in the boot part or sections 1-5', not early,
          late=[hex(r[0]) for r in early])
    if sym is not None:
        wrong = []
        for address, kind, name, tail in assemble.redirect_list(sym):
            size = 4 if kind in ('word', 'disp') else 5 + len(tail)
            data = bytes(new[address - BASE:address - BASE + size])
            got = assemble.decode_redirect(address, kind, data, tail)
            if got != sym[name]:
                wrong.append((hex(address), name, hex(sym[name]), hex(got) if got is not None else 'bad shape'))
        check(f'redirects: all {len(assemble.redirect_list(sym))} hooks reach their function in the assembled block', not wrong,
              wrong=wrong[:24])
    kept = sorted(refs_old & refs_new)
    internal = [r for r in kept if inside(r[0], [DEAD])]
    external = [r for r in kept if not inside(r[0], [DEAD])]
    unexplained = [r for r in external if r[0] not in REVIEWED]
    check('reachability: base references from outside the old handler are reviewed false positives', not unexplained,
          reviewed=[(hex(a), REVIEWED[a]) for a, *_ in external if a in REVIEWED],
          unexplained=[(hex(a), k, hex(t)) for a, k, t, _ in unexplained])
    report['dead_handler_internal_references'] = len(internal)
    report['passed'] = all(c['pass'] for c in report['checks'])
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--package', type=Path, required=True)
    ap.add_argument('--base', type=Path, required=True, help='the HSL base package (build.py base-hsl/)')
    ap.add_argument('--spec', type=Path, required=True)
    ap.add_argument('--elf', type=Path, required=True, help='assemble.py films.elf of this build (hook targets)')
    ap.add_argument('--nm', default='mn10300-elf-nm')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    report = gate(a.package, a.base, json.loads(a.spec.read_text()), assemble.symbols(a.nm, a.elf))
    text = json.dumps(report, indent=2)
    print(text)
    if a.out:
        a.out.write_text(text + '\n')
    sys.exit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
