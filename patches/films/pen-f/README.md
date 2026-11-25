# PEN-F films v1.1 / v1.2 / v1.3 source (Caduceus-style film looks)

This builds the **films-v1.1-20261119** firmware from official PEN-F 3.1 build 3101. It is the
[HSL + Live ND + AF Limiter](../../live-nd-af-limiter/pen-f/README.md) firmware with the Overlay fix, plus film
looks modelled on [caduceus-om3](https://github.com/androidfanman/caduceus-om3):

- **19 films after Color Profile 3** in the Picture Mode list (Super Control Panel / Live Control). Picking a film
  loads its look onto COLOR 3 (saturation, hue and luminance per colour, contrast, sharpness, highlights / midtones /
  shadows). The film's name shows in the list's title, and the list cursor opens on the active film.
- **WB shift per film**, added to your own WB fine-tune at capture (A-B / G-M, clamped to ±7).
- **Blacks / Whites** per film: caduceus `remapBW` on the tone curve.
- **Split toning** per film: caduceus-om3 `bend28` (Tone Balance 0) on the camera's packed R/G/B gamma table, with
  caduceus's 12-colour `st_k` table.
- Live ND (Off / 2f / 4f / 8f, Overlay fixed) and the AF Limiter as in the base firmware.

The film is recognised from COLOR 3's saturation: the settings for the list, title and WB, and each development
request's own saturation (`R+1076`) for Blacks / Whites, split toning, curves and mix. Live view, the JPEG and RAW+JPEG
follow the shot's film. **RAW Data Edit** (playback, "Current") develops with the camera's settings at the time of the
edit, so it uses the film selected **then**, not the one the photo was shot with (camera-tested with v1.3,
2026-11-25: a plain COLOR 3 RAW edited with Velvia 50 selected came out as Velvia 50). Editing saturation sectors 1–4
(1–8 from v1.2) on a film makes it COLOR 3's own look again.

The firmware still displays version 3.1. The design, every hook address and the evidence are in the
[films roadmap](../../../CADUCEUS_PENF_ROADMAP.md) and the [research notes](../../../research/penf_caduceus/README.md).

## Status

| What | Evidence |
| --- | --- |
| Films in the list, names, cursor, film loading, WB shift | camera-tested (films v1-r8 and v1.1) |
| Split toning (Superia green shadows, Portra toward cyan; no tint left on COLOR 2 / MONO after switching) | camera-tested (v1.1) |
| Blacks / Whites, split-toning strength | emulator only (bit-exact with caduceus); the camera photos were taken under different light |
| Boot, live view, burst, Live ND 4f / 8f | camera-tested (v1.1) |
| RAW Data Edit, Live ND or burst on a film | not tested |

A first v1.2 (RGB curves, Color Mix, films updated to caduceus's current looks) was built on 2026-11-20 but never
installed; its source was lost with the computer it was on. It has been rebuilt (below) without Color Mix.

## v1.2 (rebuilt 2026-11-25, not camera-tested)

**v1.2-r1 boot-looped on the camera** (package `52270e0d…ec79`, 2026-11-25; recovered with the hold-OK reflash of
v1.1). Its spec kept v1.1's bytes for the 24 hooks, but `fl_ident` had grown and every function after it had moved, so
the 16 WB-getter calls, which run at start-up in every picture mode, jumped into the middle of other code. Neither
the emulator checks (they call functions by symbol) nor the gate (it only checked that hooks land in the films
region) could see it. Now `assemble.py` generates every hook from the linked symbols (for v1.1 it reproduces all 24
camera-tested hook bytes), and `gate.py --elf` decodes each hook from the package and requires it to reach its
function: it fails r1 and passes v1.1. **v1.2-r2** (`53773a9e…39d0`) is the fixed build.

v1.1 plus:

- **RGB curves per film**: caduceus-om3 v0.30 `cv_prm` / `cv_d` (5 points per channel, -7..+7 steps of 48 on the 12-bit
  table, monotone cubic), added in the same per-entry pass as split toning, as caduceus's `st_all`:
  `t' = clamp(t + split(t) + D(t))`, kept rising. The build precomputes each channel's block (Y[5], A[4], B[4]); the
  camera evaluates the cubic. 10 of the 19 films have curves.
- **Films regraded** to caduceus-om3's current looks (`data/caduceus_om3films_d14f4e3.json`, main `d14f4e3`,
  2026-11-24): colours, tones, WB shift, Blacks / Whites (Whites now used) and split toning, all from the look data.
- **Recognition from saturation sectors 1-8** (was 1-4). With the current grades, sectors 1-4 are shared by three
  pairs of films (Portra 800 / Fuji C200, Ultramax 400 / CineStill 400D, ColorPlus 200 / Astia 100F), and sectors 1-6
  are all zero for Portra 800, which would match a plain COLOR 3. Sectors 1-8 are unique and never all zero. Editing
  any of sectors 1-8 on a film makes it COLOR 3's own look again.

**Not in v1.2: Color Mix**, which is in v1.3 (below).

| v1.2 check | Result |
| --- | --- |
| `checks.py`: fl_match, fl_ident, wb_get, st_bend, st_join, tn_tone run natively, every output bit-exact with an independent model of caduceus's maths; curve blocks equal caduceus `research/rgbcurves/model.py` for every t | pass (a corrupted curve byte fails st_bend and st_join) |
| `gate.py`: startup-safety gate, incl. every hook reaching its function | pass (v1.1 passes; v1.2-r1 fails) |
| `preflight.py`: stock updater, SD and USB-check modes, SD client / service chain, restore | pass (v1.1 passes as calibration) |
| Camera (v1.2-r2, 2026-11-25, 7 RAW+JPEG shots) | boots; films picked; the three confusable pairs recognised apart; WB shift added to the user's fine-tune, contrast and sharpness recorded right in every ORF; on a colour chart, Blacks lift (Portra 800, Ultramax 400), Portra 800's split toning (cooler shadows, warmer highlights) and Fuji C200's red curve shape are visible. Whites, exact strengths and sections 2 / 5 / 6 of TESTS-v1.2.md not yet tested |

## v1.3 (built and camera-tested 2026-11-25)

v1.2-r2 plus **Color Mix** per film (caduceus-om3 v0.30 `mx_go`, `colourmix.inc`). The hook is the matrix stage
`0x604f45a6`'s last call, the row scaler `0x604f4418` at `0x604f4649` (5 B, now `jmp mx_go`), the PEN-F counterpart
of caduceus's `.hook_mx` at OM-3 `0x6051485a`. For the development stage list's call of the stage (return
`0x604f8586`; the other caller `0x604f8ab9` stays stock) and a COLOR request without an art curve, `mx_go` recognises
the film from R+1076. It then multiplies the film's 3×3 into the matrix so far with the camera's own multiply
`0x604f41b9` (`out = (ours × so far) >> 8`), runs the stock row scaler, and returns to `0x604f464e` with d2 and d3
unchanged. The build precomputes each film's 3×3 with caduceus's model (256 = 1.0, rows summing to 256, so greys
stay grey). 12 of the 19 films have a mix. Unlike caduceus-om3, which applies the mix to photos only, our stage hooks
(split toning, curves, mix) do not test for video.

| v1.3 check | Result |
| --- | --- |
| `checks.py --release v1.3`: everything in v1.2, plus the stock multiply and row scaler equal their models (40 random matrices each), and `mx_go` run through its real hook in the stock stage code (19 films × 3 places of the matrix so far, no film, other caller, MONO, art curve) | pass (a corrupted mix value fails it) |
| `gate.py`: all 25 hooks reach their functions | pass |
| `preflight.py`: stock updater, install and restore | pass |
| Camera (2026-11-25, 9 RAW+JPEG shots + 1 RAW Data Edit) | boots; RAW Data Edit and Live ND work (owner). The PEN-F records the colour matrix it used in each file (MakerNote ImageProcessing 0x0200, twice the job's 1/128 matrix): for all 10 v1.3 photos it equals `2 × row_scaler((mix × stock) >> 8)` exactly (Velvia 50 ×3 incl. the RAW Data Edit, Gold 200, Kodachrome 64, Portra 800, CineStill 800T, Ektar 100, Ektachrome E100) or the stock matrix for a film without a mix (Ultramax 400), as for every v1.2 photo. So the hook runs on the camera, recognises the film and reaches the development job |

## Build

Requirements are the same as for the [HSL source](../../hsl/pen-f/README.md): Python 3.12 or later, GNU binutils for
`mn10300-elf` (2.45 was used), and the complete stock firmware identified in `patch.json`.

```bash
python3 patches/films/pen-f/build.py \
  --stock /path/to/OLY_E_122_3101_0000_0000.BIN \
  --out generated/pen-f-films-v1.1
```

The builder runs the HSL builder into `base-hsl/`, which checks the HSL release hash. It then checks the HSL bytes
under each of the 71 ranges in `patch.json` (by SHA-256 only), applies the new bytes and re-encodes the main
component. The OSD component is HSL's, unchanged. The output must equal the camera-tested package:

- `install/DCOLYMP/E1229999.BIN`: SHA-256 `88cf17cc2f091b8adc89e9946943373698e33aa5606b3187a9a6d84c8ba13170`,
  44,433,408 bytes.
- `restore-stock/DCOLYMP/E1229999.BIN`: stock main + OSD (`e13f9813…f26a`), the same restore as HSL.

Build v1.2 from the committed spec (or regenerate the spec with `assemble.py`, below):

```bash
python3 patches/films/pen-f/build.py --spec patches/films/pen-f/patch-v1.2.json   --stock /path/to/OLY_E_122_3101_0000_0000.BIN --out generated/pen-f-films-v1.2
```

## Assembling and checking the films block

`assemble.py` is the step that turns the source and the look data into the films block (it replaces the private
build used up to v1.1). With `--release v1.1 --check` its output equals the camera-tested block byte for byte. It
needs the decoded main of the HSL base package (from `build.py`'s `base-hsl/`) for the three stock COLOR records.

```bash
python3 patches/films/pen-f/assemble.py --release v1.2 --main hsl-main.bin --out generated/asm-v1.2   --spec-out patches/films/pen-f/patch-v1.2.json
python3 patches/films/pen-f/checks.py --release v1.2 --block generated/asm-v1.2 --caduceus ../caduceus-om3
python3 patches/films/pen-f/gate.py --package generated/pen-f-films-v1.2/install/DCOLYMP/E1229999.BIN   --base generated/pen-f-films-v1.2/base-hsl/install/DCOLYMP/E1229999.BIN --spec patches/films/pen-f/patch-v1.2.json \
  --elf generated/asm-v1.2/films.elf
python3 patches/films/pen-f/preflight.py --package generated/pen-f-films-v1.2/install/DCOLYMP/E1229999.BIN   --restore generated/pen-f-films-v1.2/restore-stock/DCOLYMP/E1229999.BIN
```

`checks.py` and `preflight.py` need the [MN103 emulator](../../../docs/tooling/EMULATOR.md).

## Files

- `patch.json`: the 71 ranges (Live ND, AF Limiter and Overlay fix as in the base firmware, plus the films). New
  bytes are this project's own code, tables and redirects; original firmware bytes are recorded only as hashes.
- `patch-v1.2.json`, `patch-v1.3.json`: the v1.2 and v1.3 specs written by `assemble.py` (camera-tested in part: see the table; it pins no package hash).
- `src/films_v1_1.s`, `src/films_v1_2.s`, `src/films_v1_3.s`: the films code (MN103 assembly) in the reclaimed `osd` debug-shell handler
  region of section 5 (`0x60a79ce0`..).
- `assemble.py`, `checks.py`, `gate.py`, `preflight.py`: assemble the block, emulator checks, startup-safety gate,
  updater preflight.
- `data/`: the film looks (caduceus-om3 v0.26.2 for v1.1, main `d14f4e3` for v1.2) and the split-toning colour
  table (caduceus-om3 `st_k`), Apache-2.0; see [the NOTICE](../../../LICENSES/caduceus-om3-NOTICE.txt).

## Install and go back

Copy `install/DCOLYMP` to the card and hold OK while switching the camera on. To go back, install
`restore-stock/DCOLYMP/E1229999.BIN` the same way. If a camera ever fails to start after an update, holding OK at
power-on and flashing the restore has recovered it (camera-tested once, for a crash after the SD updater had run).

Film names are trademarks of their owners; the looks are interpretations, not the manufacturers' own.
