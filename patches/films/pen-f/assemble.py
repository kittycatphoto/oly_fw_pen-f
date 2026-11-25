#!/usr/bin/env python3
# Copyright 2026 kittycatphoto (original contributions)
# SPDX-License-Identifier: Apache-2.0
"""Assemble the PEN-F films block (the former `osd` debug-shell handler region of section 5).

Rebuilds the step that produces the `films_60a79ce0` range in patch.json: film tables from the caduceus-om3 look
data in data/, the films source in src/, assembled and linked with GNU binutils for mn10300-elf.

  python3 assemble.py --release v1.1 --main BASE_MAIN.bin --out generated/films-osd --check
  python3 assemble.py --release v1.2 --main BASE_MAIN.bin --out generated/films-osd-v1.2 --spec-out patch-v1.2.json

BASE_MAIN is the decoded main payload of the HSL base package (the films builder's step 1); the three stock COLOR
records are copied from it, so no firmware bytes live in this repository.
  --check     v1.1 only: compare the block with patch.json's camera-tested bytes.
  --spec-out  write a patch spec for build.py: patch.json with the films block, film list and release replaced.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
CPU_BASE = 0x60021020
ORIGIN = 0x60a79ce0             # first byte after the stubbed handler entry (clr d0; rets at 0x60a79cd6)
REGION_END = 0x60a7b434         # end of the reclaimed osd handler body
FV = 0x7f00                     # film value base (picture-mode values FV..FV+NFILMS-1)
LIST_PTR = 0x60c7f7f4           # COLOR picture-mode record list pointer
TAIL_IDS = [918, 915, 973, 974, 975]   # contrast, sharpness, highlights, midtones, shadows
CURVE_STEP, CURVE_MAX = 48, 7   # caduceus-om3 v0.30 RGB curves: 5 points, offsets -7..7 steps of 48 (12-bit)
CURVE_X = [0, 1024, 2048, 3072, 4096]

# Stock and HSL addresses the films code links against (build 3101 + HSL alpha-20261017).
LINK = {
    'STOCK_SET': 0x607363b3, 'STOCK_GET': 0x60a4ff13, 'STOCK_SEL': 0x6073567b,
    'LOOKUP_RESUME': 0x60c8972f, 'setting_get': 0x602f024a, 'GETTER': 0x600750ee,
    'TONE_BUILD': 0x604f7c76, 'ST_COPY': 0x604f6140, 'ST_SKIP': 0x604f630f,
    'ST_NOCACHE': 0x604f631b, 'ST_CACHE': 0x604f62e2,
}

RELEASES = {
    # Camera-tested. Looks from caduceus-om3 v0.26.2; split toning from the owner's 2026-11-19 choices
    # (caduceus_split_v0.30.json owner_films); WB shift from patch.json. Recognition: saturation sectors 1-4.
    'v1.1': {'source': 'src/films_v1_1.s', 'looks': 'data/caduceus_om3films_v0.26.2.json',
             'split_from': 'owner_films', 'wb_from': 'spec', 'curves': False, 'ident_sectors': 4},
    # Looks, WB, split toning and RGB curves from caduceus-om3 main d14f4e3 (2026-11-24, after v0.41-beta).
    # Recognition: saturation sectors 1-8 (sectors 1-4 are shared by three pairs of the current grades).
    'v1.2': {'source': 'src/films_v1_2.s', 'looks': 'data/caduceus_om3films_d14f4e3.json',
             'split_from': 'look', 'wb_from': 'look', 'curves': True, 'ident_sectors': 8},
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def nibble(v, what):
    if not -8 <= v <= 7:
        raise ValueError(f'{what}: {v} does not fit a signed nibble')
    return v & 15


def look_values(look):
    """41 signed values: saturation, hue, luminance per sector, then contrast, sharpness, H / M / S tones."""
    tone = look.get('tone') or {}
    vals = [*look['sat'], *look['hue'], *look['light'], look.get('contrast', 0), look.get('sharp', 0),
            tone.get('highlights', 0), tone.get('midtones', 0), tone.get('shadows', 0)]
    if len(vals) != 41:
        raise ValueError(f'{look["name"]}: expected 41 values, got {len(vals)}')
    return vals


def pack_vals(vals, name):
    out = bytearray(21)
    for i, v in enumerate(vals):
        out[i >> 1] |= nibble(v, name) << (4 * (i & 1))
    return bytes(out)


def bw_record(blacks, whites):
    """caduceus-om3 bwParams / remapBW: u16 lo, u8 cB, u8 cW, u32 K (K == 0: no remap)."""
    for v in (blacks, whites):
        if not -7 <= v <= 7:
            raise ValueError(f'Blacks / Whites {v} outside -7..7')
    lo = 8 * blacks if blacks > 0 else 0
    hi = 1023 + 10 * whites if whites < 0 else 1023
    cb = -12 * blacks if blacks < 0 else 0
    cw = 12 * whites if whites > 0 else 0
    k = 0 if (blacks, whites) == (0, 0) else (hi - lo) * 1025
    return struct.pack('<HBBI', lo, cb, cw, k)


def split_record(split, st_k):
    """6 x s16: shadow K (R, G, B), highlight K (R, G, B) = st_k colour x camera steps (2 x look strength)."""
    out = []
    for colour, strength in (('sh_color', 'sh'), ('hl_color', 'hl')):
        value = (split or {}).get(strength, 0)
        steps = 2 * value
        if steps != int(steps) or not 0 <= steps <= 10:
            raise ValueError(f'split strength {value} is not 0..5 in half steps')
        rgb = st_k[(split or {}).get(colour, 0)] if steps else [0, 0, 0]
        out += [c * int(steps) for c in rgb]
    return struct.pack('<6h', *out)


def tdiv(a, b):
    """The CPU's div: truncates toward zero."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def curve_block(points):
    """caduceus-om3 cv_prm for one channel's 5 offsets -> s16 Y[5], A[4], B[4] (26 B)."""
    if len(points) != 5 or any(not -CURVE_MAX <= p <= CURVE_MAX or p != int(p) for p in points):
        raise ValueError(f'curve points {points} are not 5 integers in -7..7')
    h = [CURVE_X[i + 1] - CURVE_X[i] for i in range(4)]
    y = [p * CURVE_STEP for p in points]
    d = [tdiv((y[i + 1] - y[i]) * 4096, h[i]) for i in range(4)]
    m = [d[0], 0, 0, 0, d[3]]
    for i in range(1, 4):
        a, b = d[i - 1], d[i]
        m[i] = 0 if a == 0 or b == 0 or (a < 0) != (b < 0) else tdiv(2 * a * b, a + b)
    A = [(h[i] * m[i]) >> 12 for i in range(4)]
    B = [(h[i] * m[i + 1]) >> 12 for i in range(4)]
    return struct.pack('<13h', *y, *A, *B)


def curve_delta(block, t):
    """Reference D(t) for a 26-B channel block (caduceus cv_d), used by the checks."""
    v = struct.unpack('<13h', block)
    Y, A, B = v[:5], v[5:9], v[9:]
    i = min(3, t >> 10)
    s = ((t - CURVE_X[i]) * ((1 << 24) // 1024)) >> 12
    s2 = (s * s) >> 12
    s3 = (s2 * s) >> 12
    h00, h10, h01, h11 = 2 * s3 - 3 * s2 + 4096, s3 - 2 * s2 + s, 3 * s2 - 2 * s3, s3 - s2
    return (h00 * Y[i] + h10 * A[i] + h01 * Y[i + 1] + h11 * B[i]) >> 12


def tables(release, films, looks, split_data, color_records):
    cfg = RELEASES[release]
    by_name = {f['name']: f for f in looks['films']}
    st_k = split_data['st_k_per_step_RGB']
    wb, vals, bw, ks, names, wb_shift, curve_idx, curve_tab = (bytearray(), bytearray(), bytearray(), bytearray(),
                                                               [], [], bytearray(), bytearray())
    for film in films:
        look = by_name[film['name']]
        lwb = look.get('wb') or {'a_b': 0, 'g_m': 0}
        ab, gm = lwb['a_b'], lwb['g_m']
        if cfg['wb_from'] == 'spec':
            if [ab, gm] != film['wb_shift']:
                raise ValueError(f'{film["name"]}: WB shift differs from the look data')
        wb.append(nibble(ab, 'A-B') << 4 | nibble(gm, 'G-M'))
        wb_shift.append([ab, gm])
        vals += pack_vals(look_values(look), film['name'])
        tone = look.get('tone') or {}
        bw += bw_record(tone.get('blacks', 0), tone.get('whites', 0))
        split = split_data['owner_films'].get(film['name']) if cfg['split_from'] == 'owner_films' else None
        ks += split_record(split if cfg['split_from'] == 'owner_films' else look.get('split'), st_k)
        names.append(film['name'])
        rgb = look.get('rgb') if cfg['curves'] else None
        if rgb and any(any(rgb.get(c, [0] * 5)) for c in 'rgb'):
            if len(curve_tab) // 78 >= 255:
                raise ValueError('too many curve blocks')
            curve_idx.append(len(curve_tab) // 78)
            curve_tab += b''.join(curve_block(rgb.get(c, [0] * 5)) for c in 'rgb')
        else:
            curve_idx.append(255)
    n = cfg['ident_sectors'] // 2
    idents = [bytes(vals[i * 21:i * 21 + n]) for i in range(len(films))]
    if len(set(idents)) != len(idents):
        raise ValueError(f'Saturation sectors 1-{2 * n} must be unique per film (film recognition)')
    if any(not any(x) for x in idents):
        raise ValueError(f'A film with all-zero sectors 1-{2 * n} would match a plain COLOR 3')
    return {'wb': bytes(wb), 'vals': bytes(vals), 'bw': bytes(bw), 'k': bytes(ks), 'names': names,
            'wb_shift': wb_shift, 'color_records': color_records, 'curves': cfg['curves'],
            'curve_idx': bytes(curve_idx), 'curve_tab': bytes(curve_tab)}


def data_source(t, nfilms):
    def block(data):
        return '\n'.join('\t.byte\t' + ','.join(f'0x{b:02x}' for b in data[i:i + 16]) for i in range(0, len(data), 16))
    lines = ['\t.section .fl_wb,"a"',          # byte table straight after the code, unaligned
             '\t.global WBTAB\nWBTAB:', block(t['wb']),
             '\t.section .fl_data,"a"',        # word-aligned records; the gap is 0xff (linker FILL)
             '\t.global FL_RECS\nFL_RECS:', block(t['color_records'])]
    for j in range(nfilms):
        lines.append(f'\t.long\t{FV + j}\n\t.short\t1050,0\n\t.long\t0')
    lines += ['\t.global FL_LAB\nFL_LAB:']
    for j in range(nfilms):
        lines.append(f'\t.long\t{FV + j}\n\t.long\t5\n\t.long\tfl_name_{j}')
    lines += ['\t.global FL_VALS\nFL_VALS:', block(t['vals']), '\t.balign 4,0xff',
              '\t.global FL_TAIL\nFL_TAIL:', '\t.short\t' + ','.join(map(str, TAIL_IDS))]
    for j, name in enumerate(t['names']):
        lines.append(f'fl_name_{j}:\t.asciz\t"{name}"')
    lines += ['\t.balign 4,0xff', '\t.global FL_BW\nFL_BW:', block(t['bw']),
              '\t.global ST_K\nST_K:', block(t['k'])]
    if t['curves']:
        lines += ['\t.global CV_IDX\nCV_IDX:', block(t['curve_idx']), '\t.balign 4,0xff',
                  '\t.global CV_TAB\nCV_TAB:', block(t['curve_tab'])]
    return '\n'.join(lines) + '\n'


def tool(explicit, name):
    value = explicit or shutil.which('mn10300-elf-' + name)
    if value is None:
        raise ValueError(f'Missing mn10300-elf-{name}; supply --{name} or put it on PATH')
    return value


def assemble(release, main, spec, out, assembler, linker, objcopy):
    cfg = RELEASES[release]
    color_list = struct.unpack_from('<I', main, LIST_PTR - CPU_BASE)[0]
    color_records = bytes(main[color_list - CPU_BASE:color_list - CPU_BASE + 36])
    looks = json.loads((HERE / cfg['looks']).read_text(encoding='utf-8'))
    split = json.loads((HERE / 'data/caduceus_split_v0.30.json').read_text(encoding='utf-8'))
    films = spec['films']
    t = tables(release, films, looks, split, color_records)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'tables.s').write_text(data_source(t, len(films)))
    (out / 'layout.ld').write_text(
        'SECTIONS {\n.films 0x%08x : { *(.fl_code) FILL(0xff) . = ALIGN(2); *(.wb_get) *(.fl_wb) . = ALIGN(4); '
        '*(.fl_data) }\n/DISCARD/ : { *(*) }\n}\n' % ORIGIN
        + ''.join(f'{k} = 0x{v:08x};\n' for k, v in LINK.items()))
    defs = ['--defsym', f'FV={FV}', '--defsym', f'NFILMS={len(films)}']
    subprocess.run([assembler, *defs, '-o', str(out / 'films.o'), str(HERE / cfg['source'])], check=True)
    subprocess.run([assembler, '-o', str(out / 'tables.o'), str(out / 'tables.s')], check=True)
    subprocess.run([linker, '--no-relax', '-Map', str(out / 'films.map'), '-T', str(out / 'layout.ld'),
                    '-o', str(out / 'films.elf'), str(out / 'films.o'), str(out / 'tables.o')], check=True)
    subprocess.run([objcopy, '-O', 'binary', '--only-section=.films', str(out / 'films.elf'),
                    str(out / 'films.bin')], check=True)
    block = (out / 'films.bin').read_bytes()
    if ORIGIN + len(block) > REGION_END:
        raise ValueError(f'Films block {len(block)} B overruns the osd region')
    return block, t


def write_spec(spec, release, block, t, path, main):
    new = copy.deepcopy(spec)
    new['release'] = f'films-{release}'
    for key in ('main_sha256', 'package_sha256'):   # unknown until build.py makes it; not camera-tested
        new.pop(key, None)
    new['camera_tested'] = False
    new['films'] = [{'name': n, 'wb_shift': w} for n, w in zip(t['names'], t['wb_shift'])]
    for row in new['main_ranges']:
        if row['address'] == hex(ORIGIN):
            row['bytes'] = len(block)
            at = ORIGIN - CPU_BASE
            row['before_sha256'] = sha(bytes(main[at:at + len(block)]))   # HSL base bytes the block replaces
            row['after'] = block.hex()
            row['after_sha256'] = sha(block)
            row['purpose'] = (f'films {release}: code + wb_get + {len(t["names"])} films + B/W + split K'
                              + (' + RGB curves' if t['curves'] else '') + ' (section 5, former osd handler body)')
    path.write_text(json.dumps(new, indent=1) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release', choices=sorted(RELEASES), default='v1.1')
    ap.add_argument('--main', type=Path, required=True, help='decoded main payload of the HSL base package')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--spec', type=Path, default=HERE / 'patch.json', help='the camera-tested v1.1 spec')
    ap.add_argument('--check', action='store_true', help='v1.1: compare with the spec\'s films_60a79ce0 bytes')
    ap.add_argument('--spec-out', type=Path, help='write a build.py spec with this block')
    ap.add_argument('--as', dest='assembler')
    ap.add_argument('--ld', dest='linker')
    ap.add_argument('--objcopy')
    a = ap.parse_args()
    try:
        spec = json.loads(a.spec.read_text())
        base_main = a.main.read_bytes()
        block, t = assemble(a.release, base_main, spec, a.out, tool(a.assembler, 'as'),
                            tool(a.linker, 'ld'), tool(a.objcopy, 'objcopy'))
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError) as error:
        ap.exit(1, f'Assemble failed: {error}\n')
    report = {'release': a.release, 'bytes': len(block), 'sha256': sha(block), 'end': hex(ORIGIN + len(block)),
              'region_left': REGION_END - ORIGIN - len(block),
              'films_with_curves': sum(1 for x in t['curve_idx'] if x != 255) if t['curves'] else 0}
    if a.check:
        want = next(r for r in spec['main_ranges'] if r['address'] == hex(ORIGIN))
        expected = bytes.fromhex(want['after'])
        report['matches_spec'] = block == expected
        if block != expected:
            first = next((i for i, (x, y) in enumerate(zip(block, expected)) if x != y), min(len(block), len(expected)))
            report['first_difference'] = hex(ORIGIN + first)
    if a.spec_out:
        write_spec(spec, a.release, block, t, a.spec_out, base_main)
        report['spec_out'] = str(a.spec_out)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report.get('matches_spec', True) else 2)


if __name__ == '__main__':
    main()
