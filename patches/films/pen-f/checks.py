#!/usr/bin/env python3
# Copyright 2026 kittycatphoto (original contributions)
# SPDX-License-Identifier: Apache-2.0
"""Emulator checks for an assembled PEN-F films block (assemble.py output).

Runs the films code natively (tools/penf_emulator.py, the pinned GNU MN103 core) at its real addresses, on
synthetic requests, contexts and tables, and compares every result with an independent Python model of
caduceus-om3's maths (bend28 split toning, cv_prm / cv_d RGB curves, remapBW). The stock functions the films code
calls (setting_get, the WB getter, the tone-LUT builder) are replaced by small stand-ins, assembled here.

  python3 checks.py --release v1.2 --block generated/asm-v12 [--caduceus ../caduceus-om3]

Not covered: the image processor's use of the tables, live-view cost, task scheduling, the stock RGB stage and
tone builder themselves (the stage-list call sites are byte-checked by build.py).
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from penf_emulator import Region, execute, STACK, INITIAL_SP, WRAPPER  # noqa: E402
import assemble  # noqa: E402

MEM = 0x10000000                 # synthetic data (R, C, O, tables, settings)
R_ADDR, C_ADDR, O_ADDR = MEM, MEM + 0x1000, MEM + 0x2000
SET_ADDR = MEM + 0x8000          # settings for the setting_get stand-in
TABLE_A, TABLE_B = MEM + 0x4000, MEM + 0x4800
STAGE_SP = STACK + 0x800         # the RGB stage's sp at the join
MASK = 0xf0                      # [d2,d3,a2,a3]
KEY_AB, KEY_GM = 0x84f9, 0x9679
U32 = 0xffffffff
SAT = 1076


def signed(v):
    return v - (1 << 32) if v & 0x80000000 else v


class Films:
    def __init__(self, release, block_dir, toolchain):
        self.release = release
        self.block = (block_dir / 'films.bin').read_bytes()
        self.sym = {}
        nm = subprocess.run([toolchain('nm'), str(block_dir / 'films.elf')], capture_output=True, text=True, check=True)
        for line in nm.stdout.splitlines():
            parts = line.split()
            if len(parts) == 3:
                self.sym[parts[2]] = int(parts[0], 16)
        spec = json.loads((HERE / 'patch.json').read_text())
        cfg = assemble.RELEASES[release]
        looks = json.loads((HERE / cfg['looks']).read_text(encoding='utf-8'))
        split = json.loads((HERE / 'data/caduceus_split_v0.30.json').read_text(encoding='utf-8'))
        color = bytes(36)  # not executed by these checks
        self.t = assemble.tables(release, spec['films'], looks, split, color)
        self.by_name = {f['name']: f for f in looks['films']}
        self.names = self.t['names']
        self.n = len(self.names)
        self.ident = cfg['ident_sectors']
        self.stubs = self._stubs(toolchain)

    def _stubs(self, toolchain):
        """setting_get (d0 id -> value), WB getter (-> the user's fine-tune) and a tone builder that changes nothing."""
        src = f'''
	.section .sg,"ax"
sg:	cmp	111,d0
	bne	1f
	movbu	({SET_ADDR}),d0
	ret	[],4
1:	cmp	1086,d0
	bne	2f
	movbu	({SET_ADDR + 1}),d0
	ret	[],4
2:	add	-955,d0
	mov	{SET_ADDR + 2},a0
	add	d0,a0
	movbu	(a0),d0
	extb	d0
	ret	[],4
	.section .getter,"ax"
	movbu	({SET_ADDR + 16}),d0
	extb	d0
	ret	[d2,d3],12
	.section .tone,"ax"
	ret	[d2,d3,a2,a3],28
'''
        work = HERE.parents[2] / 'generated' / 'films-checks'
        work.mkdir(parents=True, exist_ok=True)
        (work / 'stubs.s').write_text(src)
        (work / 'stubs.ld').write_text(
            'SECTIONS {\n.sg 0x%08x : { *(.sg) }\n.getter 0x%08x : { *(.getter) }\n.tone 0x%08x : { *(.tone) }\n}\n'
            % (assemble.LINK['setting_get'], assemble.LINK['GETTER'], assemble.LINK['TONE_BUILD']))
        subprocess.run([toolchain('as'), '-o', str(work / 'stubs.o'), str(work / 'stubs.s')], check=True)
        subprocess.run([toolchain('ld'), '--no-relax', '-T', str(work / 'stubs.ld'), '-o', str(work / 'stubs.elf'),
                        str(work / 'stubs.o')], check=True)
        out = {}
        for name, key in (('sg', 'setting_get'), ('getter', 'GETTER'), ('tone', 'TONE_BUILD')):
            subprocess.run([toolchain('objcopy'), '-O', 'binary', f'--only-section=.{name}', str(work / 'stubs.elf'),
                            str(work / f'{name}.bin')], check=True)
            out[key] = (work / f'{name}.bin').read_bytes()
        return out

    def regions(self, extra=()):
        base = [Region('films', assemble.ORIGIN, self.block, 'rx'),
                Region('stack', STACK, bytes(0x1100), 'rw')]
        base += [Region(f'stub_{k}', assemble.LINK[k], v, 'rx') for k, v in self.stubs.items()]
        return base + list(extra)

    def call(self, name, frame, registers, extra, *, mask=MASK, limit=2_000_000):
        target = self.sym[name]
        code = b'\xdd' + struct.pack('<i', target - WRAPPER) + bytes([mask, frame])
        regs = {'d2': 0x22334455, 'd3': 0x66778899, 'a2': 0xaabbccdd, 'a3': 0x11223344, 'sp': INITIAL_SP, 'pc': WRAPPER}
        regs.update(registers)
        r = execute([Region('caller', WRAPPER, code, 'rx')] + self.regions(extra), regs, WRAPPER + len(code),
                    limit=limit, timeout=120)
        return r, regs

    # ---- reference models (independent of the code under test)
    def film_sat(self, j):
        return self.by_name[self.names[j]]['sat']

    def k_record(self, j):
        return struct.unpack('<6h', self.t['k'][12 * j:12 * j + 12])

    def curve(self, j):
        idx = self.t['curve_idx'][j] if self.t['curves'] else 255
        return None if idx == 255 else self.t['curve_tab'][78 * idx:78 * idx + 78]

    def ref_bend(self, words, j):
        ks = self.k_record(j)
        cv = self.curve(j)
        out = list(words)
        for c in range(3):
            mx = 0
            for e, w in enumerate(words):
                v = (w >> (10 * c)) & 1023
                t = v << 2 | v >> 8
                s = 4095 - t
                ws = ((t * s >> 12) * s) >> 12
                wh = ((t * t >> 12) * s) >> 12
                d = (ks[c] * ws + ks[3 + c] * wh) >> 9
                if cv:
                    d += assemble.curve_delta(cv[26 * c:26 * c + 26], t)
                u = max(0, min(4095, t + d))
                mx = max(mx, u)
                out[e] = (out[e] & ~(1023 << (10 * c)) & U32) | ((mx >> 2) << (10 * c))
        return out

    def ref_bw(self, lut, j):
        lo, cb, cw, k = struct.unpack('<HBBI', self.t['bw'][8 * j:8 * j + 8])
        out, prev = [], 0
        for v in lut:
            y = min(v, 1023)
            tt = 1023 - y
            y -= (cb * ((((tt * tt) >> 10) * tt) >> 10)) >> 10
            y = max(y, 0)
            y += (cw * ((((y * y) >> 10) * y) >> 10)) >> 10
            y = min(y, 1023)
            y = lo + (((y * k) & U32) + 0xfffff & U32) // 0x100000   # unsigned 32-bit, as mulu/add/lsr
            y = max(y, prev)
            prev = y
            out.append(y)
        return out


def gamma_table(offsets=(0, 0, 0)):
    words = []
    for e in range(256):
        base = round(1023 * (e / 255) ** (1 / 2.2))
        ch = [max(0, min(1023, base + o)) for o in offsets]
        words.append(ch[0] | ch[1] << 10 | ch[2] << 20)
    return words


def sat_bytes(sat):
    return bytes(x & 0xff for x in sat) + bytes(12 - len(sat))


def checks(f, caduceus):
    results = []

    def check(name, ok, detail=''):
        results.append({'check': name, 'pass': bool(ok), **({'detail': detail} if detail else {})})

    # 1. fl_match: every film's own saturation, a plain COLOR 3, a changed last identifying sector
    if 'fl_match' in f.sym:
        bad = []
        cases = [(j, f.film_sat(j)) for j in range(f.n)]
        cases.append((-1, [0] * 12))
        for j in range(f.n):
            changed = list(f.film_sat(j))
            changed[f.ident - 1] = changed[f.ident - 1] + 1 if changed[f.ident - 1] < 7 else -8
            cases.append((-2, changed))
        for want, sat in cases:
            r, _ = f.call('fl_match', 32, {'a1': MEM}, [Region('sat', MEM, sat_bytes(sat), 'r')])
            got = signed(r['registers']['d0'])
            expect = want if want != -2 else -1
            if want == -2 and got != -1:
                # another film may legitimately own the changed value
                own = [k for k in range(f.n) if f.film_sat(k)[:f.ident] == sat[:f.ident]]
                expect = own[0] if own else -1
            if r['fault'] or got != expect or r['registers']['d2'] != 0x22334455:
                bad.append((want, got, r['fault']))
        check(f'fl_match: {len(cases)} saturation sets (19 films, plain COLOR 3, sector {f.ident} changed)', not bad,
              str(bad[:3]))

    # 2. fl_ident + wb_get through the setting_get / getter stand-ins
    def settings(mode, profile, sat, user_wb):
        data = bytearray(32)
        data[0], data[1] = mode, profile
        data[2:2 + 12] = sat_bytes(sat)
        data[16] = user_wb & 0xff
        return Region('settings', SET_ADDR, bytes(data), 'r')

    bad = []
    for j in range(f.n):
        for mode, profile, film_expected in ((56, 0, True), (11, 3, True), (11, 2, False), (57, 3, False)):
            r, _ = f.call('fl_ident', 32, {}, [settings(mode, profile, f.film_sat(j), 0)])
            got = signed(r['registers']['d0'])
            want = j if film_expected else -1
            if r['fault'] or got != want:
                bad.append((f.names[j], mode, profile, got))
    check('fl_ident: 19 films x COLOR 3 as mode 56 / mode 11 + profile 3, and not COLOR 3', not bad, str(bad[:3]))

    bad = []
    for j in range(f.n):
        ab, gm = f.t['wb_shift'][j]
        for key, shift in ((KEY_AB, ab), (KEY_GM, gm), (0x1234, 0)):
            for user in (-7, -3, 0, 4, 7):
                r, _ = f.call('wb_get', 12, {'d0': key, 'd1': 0, 'a0': 0}, [settings(56, 0, f.film_sat(j), user)],
                              mask=0xc0)
                got = signed(r['registers']['d0'])
                want = max(-7, min(7, user + shift)) if key != 0x1234 else user
                if r['fault'] or got != want:
                    bad.append((f.names[j], hex(key), user, got, want))
    check('wb_get: film WB shift added to the user fine-tune, clamped to +-7; other keys unchanged', not bad, str(bad[:3]))

    # 3. st_bend direct: split toning + RGB curves on two tables (equal and unequal channels), both banks
    bad, ran = [], 0
    for j in range(f.n):
        ks, cv = f.k_record(j), f.curve(j)
        if not any(ks) and not cv:
            continue
        for offsets in ((0, 0, 0), (9, -14, 23)):
            words = gamma_table(offsets)
            data = struct.pack('<256I', *words)
            d2 = (f.sym['CV_TAB'] + 78 * f.t['curve_idx'][j]) if cv else 0
            r, _ = f.call('st_bend', 56, {'a0': TABLE_A, 'a3': f.sym['ST_K'] + 12 * j, 'd2': d2},
                          [Region('table', TABLE_A, data, 'rw', capture=True)])
            got = list(struct.unpack('<256I', bytes.fromhex(r['memory'][0]['hex'])))
            want = f.ref_bend(words, j)
            ran += 1
            if r['fault'] or got != want or r['registers']['d2'] != d2:
                first = next((e for e in range(256) if got[e] != want[e]), None)
                bad.append((f.names[j], offsets, first, r['fault']))
    check(f'st_bend: {ran} film/table runs bit-exact with caduceus bend28 + cv_d', not bad and ran, str(bad[:3]))

    # 4. st_join: the whole join (recognition from R+1076, C+100 |= 3, both banks, registers, exit)
    def join(sat, key=0x000b0000, art=0, d2=1, bank_b=True):
        req = bytearray(2048)
        struct.pack_into('<I', req, 8, key)
        struct.pack_into('<I', req, 960, art)
        req[SAT:SAT + 12] = sat_bytes(sat)
        ctx = bytearray(256)
        struct.pack_into('<I', ctx, 100, 0x40)
        out = bytearray(2048)
        struct.pack_into('<I', out, 1052, TABLE_A)
        struct.pack_into('<I', out, 1056, TABLE_B if bank_b else 0)
        stage = bytearray(0x800 + 0x100)
        sp_off = 0x800
        for off, val in ((52, R_ADDR), (56, C_ADDR), (28, O_ADDR), (64, 0x5a5a1234)):
            struct.pack_into('<I', stage, sp_off + off, val)
        ta, tb = gamma_table(), gamma_table((5, -3, 11))
        regions = [Region('films', assemble.ORIGIN, f.block, 'rx'),
                   Region('stage', STACK, bytes(stage), 'rw'),
                   Region('req', R_ADDR, bytes(req), 'r'), Region('ctx', C_ADDR, bytes(ctx), 'rw', capture=True),
                   Region('out', O_ADDR, bytes(out), 'r'),
                   Region('ta', TABLE_A, struct.pack('<256I', *ta), 'rw', capture=True),
                   Region('tb', TABLE_B, struct.pack('<256I', *tb), 'rw', capture=True)]
        regs = {'d2': d2, 'd3': 0x66778899, 'a2': 0xaabbccdd, 'a3': 0x11223344, 'sp': STACK + sp_off,
                'pc': f.sym['st_join']}
        stop = assemble.LINK['ST_CACHE'] if d2 else assemble.LINK['ST_NOCACHE']
        r = execute(regions, regs, stop, limit=4_000_000, timeout=120)
        mem = {m['name']: bytes.fromhex(m['hex']) for m in r['memory']}
        return r, regs, mem, ta, tb

    bad = []
    for j in range(f.n):
        for d2 in (1, 0):
            r, regs, mem, ta, tb = join(f.film_sat(j), d2=d2)
            ga = list(struct.unpack('<256I', mem['ta']))
            gb = list(struct.unpack('<256I', mem['tb']))
            has = any(f.k_record(j)) or f.curve(j) is not None
            wa = f.ref_bend(ta, j) if has else ta
            wb = f.ref_bend(tb, j) if has else tb
            stop = assemble.LINK['ST_CACHE'] if d2 else assemble.LINK['ST_NOCACHE']
            ok = (not r['fault'] and r['registers']['pc'] == stop and ga == wa and gb == wb
                  and struct.unpack_from('<I', mem['ctx'], 100)[0] == 0x43
                  and all(r['registers'][k] == regs[k] for k in ('d2', 'd3', 'a2', 'a3', 'sp'))
                  and (not d2 or r['registers']['d0'] == 0x5a5a1234))
            if not ok:
                bad.append((f.names[j], d2, r['fault'], ga == wa, gb == wb))
    for label, kw in (('no film', {'sat': [0] * 12}), ('MONO-like key', {'sat': f.film_sat(0), 'key': 0x000c0000}),
                      ('art curve', {'sat': f.film_sat(0), 'art': 0x60600000}),
                      ('bank B unused', {'sat': f.film_sat(0), 'bank_b': False})):
        r, regs, mem, ta, tb = join(**kw)
        ga = list(struct.unpack('<256I', mem['ta']))
        gb = list(struct.unpack('<256I', mem['tb']))
        c100 = struct.unpack_from('<I', mem['ctx'], 100)[0]
        if label == 'bank B unused':
            ok = ga == f.ref_bend(ta, 0) and gb == tb and c100 == 0x43
        elif label == 'no film':
            ok = ga == ta and gb == tb and c100 == 0x43
        else:
            ok = ga == ta and gb == tb and c100 == 0x40
        ok = ok and not r['fault'] and all(r['registers'][k] == regs[k] for k in ('d2', 'd3', 'a2', 'a3', 'sp'))
        if not ok:
            bad.append((label, r['fault'], ga == ta, gb == tb, hex(c100)))
    check('st_join: 19 films x both exits; no film, other modes, art curve and one bank stay stock', not bad, str(bad[:3]))

    # 5. tn_tone: recognition from R+1076 and Blacks / Whites on a 10-bit LUT (tone builder stand-in)
    lut = [min(1023, round(1023 * (e / 255) ** 0.9)) for e in range(256)]
    bad = []
    for j in list(range(f.n)) + [-1]:
        sat = f.film_sat(j) if j >= 0 else [0] * 12
        req = bytearray(2048)
        struct.pack_into('<I', req, 8, 0x000b0000)
        req[SAT:SAT + 12] = sat_bytes(sat)
        ctx = bytearray(256)
        struct.pack_into('<I', ctx, 4, R_ADDR)
        struct.pack_into('<I', ctx, 12, O_ADDR)
        struct.pack_into('<I', ctx, 56, 0x100)
        out = bytearray(0x1500)
        struct.pack_into('<I', out, 0x1230, TABLE_A)
        r, regs = f.call('tn_tone', 28, {'d3': C_ADDR},
                         [Region('req', R_ADDR, bytes(req), 'r'), Region('ctx', C_ADDR, bytes(ctx), 'rw', capture=True),
                          Region('out', O_ADDR, bytes(out), 'rw', capture=True),
                          Region('lut', TABLE_A, struct.pack('<256H', *lut), 'r')])
        mem = {m['name']: bytes.fromhex(m['hex']) for m in r['memory']}
        o = mem['out']
        active = struct.unpack_from('<I', o, 0x1230)[0]
        has_bw = j >= 0 and struct.unpack_from('<I', f.t['bw'], 8 * j + 4)[0] != 0
        if has_bw:
            got = list(struct.unpack_from('<256H', o, 0x1234))
            ok = active == O_ADDR + 0x1234 and got == f.ref_bw(lut, j)
        else:
            ok = active == TABLE_A and o[0x1234:0x1434] == bytes(512)
        ok = ok and not r['fault'] and struct.unpack_from('<I', mem['ctx'], 56)[0] == 0x100
        if not ok:
            bad.append((f.names[j] if j >= 0 else 'no film', r['fault'], hex(active)))
    n_bw = sum(1 for j in range(f.n) if struct.unpack_from('<I', f.t['bw'], 8 * j + 4)[0])
    check(f'tn_tone: 19 films + no film; {n_bw} Blacks / Whites remaps bit-exact with caduceus remapBW', not bad,
          str(bad[:3]))

    # 6. the curve model against caduceus-om3's own research/rgbcurves/model.py, every t, every film
    if caduceus and f.t['curves']:
        path = caduceus / 'research/rgbcurves/model.py'
        spec = importlib.util.spec_from_file_location('cad_rgb', path)
        cad = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cad)
        bad = []
        for j in range(f.n):
            rgb = f.by_name[f.names[j]].get('rgb')
            cv = f.curve(j)
            if not cv:
                continue
            for c, ch in enumerate('rgb'):
                pts = rgb.get(ch, [0] * 5)
                p = cad.prm([pts[0], 0, pts[1], pts[2], pts[3], pts[4]])
                for t in range(4096):
                    if cad.d_at(p, t) != assemble.curve_delta(cv[26 * c:26 * c + 26], t):
                        bad.append((f.names[j], ch, t))
                        break
        check('curve blocks: D(t) equals caduceus-om3 model.py for every t, channel and film', not bad, str(bad[:3]))
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--release', choices=sorted(assemble.RELEASES), default='v1.2')
    ap.add_argument('--block', type=Path, required=True, help='assemble.py --out directory')
    ap.add_argument('--caduceus', type=Path, help='a caduceus-om3 checkout, for the curve cross-check')
    ap.add_argument('--out', type=Path, help='write the report as JSON')
    a = ap.parse_args()

    def toolchain(name):
        value = shutil.which('mn10300-elf-' + name)
        if not value:
            ap.exit(1, f'mn10300-elf-{name} not on PATH\n')
        return value

    films = Films(a.release, a.block, toolchain)
    results = checks(films, a.caduceus)
    report = {'release': a.release, 'block_sha256': assemble.sha(films.block), 'camera_access': False,
              'passed': all(r['pass'] for r in results), 'checks': results}
    text = json.dumps(report, indent=2)
    print(text)
    if a.out:
        a.out.write_text(text + '\n')
    sys.exit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
