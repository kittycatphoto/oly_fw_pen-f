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
    # v1.3 Color Mix: the matrix stage's 3 x 3 multiply and row scaler, the return after the hook, and the return
    # address of the development stage list's call of the matrix stage (0x604f8581).
    'MX_MUL': 0x604f41b9, 'MX_ROW': 0x604f4418, 'MX_BACK': 0x604f464e, 'MX_RET': 0x604f8586,
}
MIX_UNIT = 8                    # caduceus-om3 colourmix: one hue / strength step = 8 / 256

# Every redirect from stock code into the films block, generated from the linked symbols (v1.2-r1 copied v1.1's
# bytes, so its hooks pointed at v1.1's addresses: boot loop). (address, kind, symbol, tail bytes):
#   word   - absolute 32-bit pointer
#   jmp    - `jmp d32` (dc + rel32 from the address), then the tail (nops)
#   call   - `call d32,[regs],frame` (dd + rel32), then the tail (register mask, frame)
#   disp   - the 4-byte displacement of an existing `call d32` whose opcode is the byte before the address
WB_SITES = [0x6054f1e6, 0x6054f200, 0x6054f343, 0x6054f358, 0x6054f3d5, 0x6054f3eb, 0x6054f4c3, 0x6054f4db,
            0x6054f52f, 0x6054f548, 0x60557425, 0x6055743a, 0x60567dd4, 0x60567dec, 0x60af551c, 0x60af5530]
REDIRECTS = [
    (0x604f6139, 'jmp', 'st_gate', bytes.fromhex('cbcb')),     # RGB stage cache-hit skip
    (0x604f62dc, 'jmp', 'st_join', bytes.fromhex('cb')),       # RGB stage join after the copier
    (0x604f85e8, 'call', 'tn_tone', bytes.fromhex('f01c')),    # tone-LUT builder call, [d2,d3,a2,a3],28
    (0x609a4660, 'word', 'fl_set', b''),                       # facade slot 0
    (0x609a4668, 'word', 'fl_get', b''),                       # facade slot 2
    (0x609a4684, 'word', 'fl_sel', b''),                       # facade slot 9
    (0x60c7f7f4, 'word', 'FL_RECS', b''),                      # COLOR picture-mode record list
    (0x60c8972a, 'jmp', 'fl_lk', b''),                         # label lookup entry
    *[(site + 1, 'disp', 'wb_get', b'') for site in WB_SITES],  # WB fine-tune reads
]


MIX_REDIRECT = (0x604f4649, 'jmp', 'mx_go', b'')   # matrix stage row-scaler call (v1.3)


def redirect_list(sym):
    """The hooks of a build: the v1.1 / v1.2 set, plus Color Mix's when the block has mx_go."""
    return REDIRECTS + ([MIX_REDIRECT] if 'mx_go' in sym else [])


def redirect_bytes(address, kind, target, tail):
    if kind == 'word':
        return struct.pack('<I', target)
    if kind == 'disp':
        return struct.pack('<i', target - (address - 1))
    return bytes([0xdc if kind == 'jmp' else 0xdd]) + struct.pack('<i', target - address) + tail


def decode_redirect(address, kind, data, tail):
    """The target a redirect's bytes actually reach (None when its shape is wrong)."""
    if kind == 'word':
        return struct.unpack('<I', data)[0] if len(data) == 4 else None
    if kind == 'disp':
        return (address - 1 + struct.unpack('<i', data)[0]) & 0xffffffff if len(data) == 4 else None
    op = 0xdc if kind == 'jmp' else 0xdd
    if len(data) != 5 + len(tail) or data[0] != op or data[5:] != tail:
        return None
    return (address + struct.unpack_from('<i', data, 1)[0]) & 0xffffffff


def symbols(nm, elf):
    out = subprocess.run([nm, str(elf)], capture_output=True, text=True, check=True).stdout
    return {p[2]: int(p[0], 16) for p in (line.split() for line in out.splitlines()) if len(p) == 3}


RELEASES = {
    # Camera-tested. Looks from caduceus-om3 v0.26.2; split toning from the owner's 2026-11-19 choices
    # (caduceus_split_v0.30.json owner_films); WB shift from patch.json. Recognition: saturation sectors 1-4.
    'v1.1': {'source': 'src/films_v1_1.s', 'looks': 'data/caduceus_om3films_v0.26.2.json',
             'split_from': 'owner_films', 'wb_from': 'spec', 'curves': False, 'ident_sectors': 4},
    # Looks, WB, split toning and RGB curves from caduceus-om3 main d14f4e3 (2026-11-24, after v0.41-beta).
    # Recognition: saturation sectors 1-8 (sectors 1-4 are shared by three pairs of the current grades).
    'v1.2': {'source': 'src/films_v1_2.s', 'looks': 'data/caduceus_om3films_d14f4e3.json',
             'split_from': 'look', 'wb_from': 'look', 'curves': True, 'ident_sectors': 8},
    # v1.2 + per-film Color Mix (caduceus-om3 v0.30 mx_go) in the camera's colour-matrix stage.
    'v1.3': {'source': 'src/films_v1_3.s', 'looks': 'data/caduceus_om3films_d14f4e3.json',
             'split_from': 'look', 'wb_from': 'look', 'curves': True, 'ident_sectors': 8, 'mix': True},
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


def mix_matrix(v):
    """caduceus-om3 research/colourmix/model.py: [h R, s R, h G, s G, h B, s B] (-7..7) -> 3 x 3 rows, 256 = 1.0."""
    if len(v) != 6 or any(not -7 <= x <= 7 or x != int(x) for x in v):
        raise ValueError(f'mix {v} is not 6 integers in -7..7')
    m = [[0] * 3 for _ in range(3)]
    for j in range(3):
        h, s = v[2 * j], v[2 * j + 1]
        m[(j + 1) % 3][j] = MIX_UNIT * (h - s)
        m[(j + 2) % 3][j] = MIX_UNIT * (-h - s)
    for i in range(3):
        m[i][i] = 256 - sum(m[i][c] for c in range(3) if c != i)
    return m


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
    mix_idx, mix_tab = bytearray(), bytearray()
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
        mix = look.get('mix') if cfg.get('mix') else None
        if mix and any(mix):
            mix_idx.append(len(mix_tab) // 18)
            mix_tab += struct.pack('<9h', *[x for row in mix_matrix(mix) for x in row])
        else:
            mix_idx.append(255)
    n = cfg['ident_sectors'] // 2
    idents = [bytes(vals[i * 21:i * 21 + n]) for i in range(len(films))]
    if len(set(idents)) != len(idents):
        raise ValueError(f'Saturation sectors 1-{2 * n} must be unique per film (film recognition)')
    if any(not any(x) for x in idents):
        raise ValueError(f'A film with all-zero sectors 1-{2 * n} would match a plain COLOR 3')
    return {'wb': bytes(wb), 'vals': bytes(vals), 'bw': bytes(bw), 'k': bytes(ks), 'names': names,
            'wb_shift': wb_shift, 'color_records': color_records, 'curves': cfg['curves'],
            'curve_idx': bytes(curve_idx), 'curve_tab': bytes(curve_tab),
            'mix': bool(cfg.get('mix')), 'mix_idx': bytes(mix_idx), 'mix_tab': bytes(mix_tab)}


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
    if t['mix']:
        lines += ['\t.global MX_IDX\nMX_IDX:', block(t['mix_idx']), '\t.balign 4,0xff',
                  '\t.global MX_TAB\nMX_TAB:', block(t['mix_tab'])]
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
    sym = symbols(str(Path(objcopy).with_name(Path(objcopy).name.replace('objcopy', 'nm'))), out / 'films.elf')
    hooks = redirect_list(sym)
    redirects = {address: redirect_bytes(address, kind, sym[name], tail) for address, kind, name, tail in hooks}
    (out / 'redirects.json').write_text(json.dumps(
        {hex(a): {'kind': k, 'symbol': n, 'target': hex(sym[n]), 'bytes': redirects[a].hex()}
         for a, k, n, _ in hooks}, indent=1) + '\n')
    return block, t, redirects


def write_spec(spec, release, block, t, path, main, redirects):
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
    rows = {int(r['address'], 16): r for r in new['main_ranges']}
    for address, data in redirects.items():
        if address not in rows:                  # a hook new in this release (v1.3: Color Mix)
            at = address - CPU_BASE
            rows[address] = {'name': f'films_mix_{address:08x}', 'feature': 'films_mix', 'address': hex(address),
                             'bytes': len(data), 'before_sha256': sha(bytes(main[at:at + len(data)])),
                             'purpose': f'v1.3: matrix stage row-scaler call at {hex(address)} -> jmp mx_go'}
            new['main_ranges'].append(rows[address])
        row = rows[address]                      # every redirect is a range of the same length
        if row['bytes'] != len(data):
            raise ValueError(f'redirect {hex(address)}: {len(data)} B, range has {row["bytes"]}')
        row['after'] = data.hex()
        row['after_sha256'] = sha(data)
    new['main_ranges'].sort(key=lambda r: int(r['address'], 16))
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
        block, t, redirects = assemble(a.release, base_main, spec, a.out, tool(a.assembler, 'as'),
                                       tool(a.linker, 'ld'), tool(a.objcopy, 'objcopy'))
    except (ValueError, OSError, subprocess.CalledProcessError, KeyError) as error:
        ap.exit(1, f'Assemble failed: {error}\n')
    report = {'release': a.release, 'bytes': len(block), 'sha256': sha(block), 'end': hex(ORIGIN + len(block)),
              'region_left': REGION_END - ORIGIN - len(block),
              'films_with_curves': sum(1 for x in t['curve_idx'] if x != 255) if t['curves'] else 0,
              'films_with_mix': sum(1 for x in t['mix_idx'] if x != 255) if t['mix'] else 0}
    if a.check:
        want = next(r for r in spec['main_ranges'] if r['address'] == hex(ORIGIN))
        expected = bytes.fromhex(want['after'])
        report['matches_spec'] = block == expected
        if block != expected:
            first = next((i for i, (x, y) in enumerate(zip(block, expected)) if x != y), min(len(block), len(expected)))
            report['first_difference'] = hex(ORIGIN + first)
        rows = {int(r['address'], 16): bytes.fromhex(r['after']) for r in spec['main_ranges']}
        wrong = [hex(x) for x, data in redirects.items() if rows.get(x) != data]
        report['redirects_match_spec'] = not wrong
        report['matches_spec'] = report['matches_spec'] and not wrong
        if wrong:
            report['redirects_differ'] = wrong
    if a.spec_out:
        write_spec(spec, a.release, block, t, a.spec_out, base_main, redirects)
        report['spec_out'] = str(a.spec_out)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report.get('matches_spec', True) else 2)


if __name__ == '__main__':
    main()
