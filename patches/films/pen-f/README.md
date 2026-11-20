# PEN-F films v1.1 source (Caduceus-style film looks)

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

The film is recognised from COLOR 3's saturation: the settings for the list, title and WB, and each photo's own
request (`R+1076`) for Blacks / Whites and split toning. So live view, the JPEG, RAW+JPEG and in-camera RAW edit each
follow the photo's own film. Editing saturation sectors 1–4 on a film makes it COLOR 3's own look again.

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

A v1.2 (RGB curves, Color Mix, films updated to caduceus's current looks) was built and passed the emulator checks
and the updater preflight, but was never installed; it is not in this package.

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

## Files

- `patch.json`: the 71 ranges (Live ND, AF Limiter and Overlay fix as in the base firmware, plus the films). New
  bytes are this project's own code, tables and redirects; original firmware bytes are recorded only as hashes.
- `src/films_v1_1.s`: the films code (MN103 assembly) in the reclaimed `osd` debug-shell handler region of section 5
  (`0x60a79ce0`..), assembled with the film tables by the author's private build; the `osd` block in `patch.json`
  is its output.
- `data/`: the film looks (caduceus-om3 v0.26.2 Look Lab data) and the split-toning colour table (caduceus-om3
  `st_k`), Apache-2.0; see [the NOTICE](../../../LICENSES/caduceus-om3-NOTICE.txt).

## Install and go back

Copy `install/DCOLYMP` to the card and hold OK while switching the camera on. To go back, install
`restore-stock/DCOLYMP/E1229999.BIN` the same way. If a camera ever fails to start after an update, holding OK at
power-on and flashing the restore has recovered it (camera-tested once, for a crash after the SD updater had run).

Film names are trademarks of their owners; the looks are interpretations, not the manufacturers' own.
