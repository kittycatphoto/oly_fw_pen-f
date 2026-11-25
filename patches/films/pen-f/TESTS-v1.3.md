# PEN-F films v1.3: camera test plan

Package: `DCOLYMP/E1229999.BIN`, **v1.3**, SHA-256 `90e2bb291ab52df52cf9e034f4a420a3ae2953b8bd855184b980e8d994fadd9a`
(built 2026-11-25). It is v1.2-r2 (camera-tested: boots, films, WB shift, Blacks, split toning, RGB curves) plus
**Color Mix** per film: a 3×3 colour matrix put into the camera's own colour-matrix stage, as caduceus-om3 v0.30.
It costs no extra processing time per photo.

Already checked without the camera:
- **Emulator:** the camera's own multiply and row scaler match their models; `mx_go` runs through its real hook in
  the stock matrix stage for every film, plus no film, the other caller, MONO and art curves.
- **Startup-safety gate:** passes, including all 25 hooks reaching their functions.
- **Updater preflight.**

The Color Mix hook is new code in the image pipeline. It is not in start-up, and it runs only for COLOR photos and
live view with a film. Still, **stop at the first boot problem** and go to [Recovery](#recovery).

## 1. Start-up

- [ ] Hold **OK** while switching on, install. The camera starts to live view.
- [ ] Switch off and on 3 times, once with a film selected.

## 2. Color Mix on the films

Same chart scene, same light and exposure as the v1.2 shots. Shoot RAW+JPEG on plain Color Profile 3, then the
films below. The mix only changes colours, so the grey row should stay as it was in v1.2 (no new tint).

| Film | Mix (caduceus Look Lab terms) |
| --- | --- |
| Gold 200 | green weaker 2, blue stronger 1 |
| Kodachrome 64 | green toward cyan 1, green weaker 1 |
| Portra 800 | green toward yellow 1 |
| CineStill 800T | red toward yellow 1, red weaker 1, green weaker 2, blue stronger 1 |
| Ektar 100 | red stronger 2, green toward cyan 1, green stronger 1, blue weaker 1 |
| Pro 400H | red toward yellow 1, red stronger 1, green weaker 1, blue stronger 1 |
| **Velvia 50** | red toward yellow 1, red stronger 1, **green toward cyan 7**, blue toward purple 2, blue weaker 1 |
| Superia 400 | green weaker 2 |
| ColorPlus 200 | green toward yellow 2, green weaker 3, blue toward cyan 1, blue stronger 1 |
| Fuji C200 | green toward yellow 1, green weaker 2, blue stronger 1 |
| **Ektachrome E100** | red toward magenta 1, **green toward cyan 6**, blue toward purple 1, blue weaker 1 |
| Provia 100F | green toward cyan 2, green weaker 1, blue toward purple 1 |

The other 7 films have no mix (same as v1.2).

- [ ] **Velvia 50** and **Ektachrome E100** first: they have the strongest mix, so greens should clearly lean
      toward cyan compared with v1.2.
- [ ] The grey row stays neutral, as in v1.2, on every film (a mix keeps greys grey).
- [ ] No banding, posterising, wrong or swapped colours, or black frames.
- [ ] Live view shows the mix as well (it runs in the same stage as photos).
- [ ] Plain Color Profile 1 / 2 / 3, Monochrome and an Art Filter look as before.

## 3. Still open from v1.2

- [ ] Scroll quickly through all films, several times.
- [ ] **RAW Data Edit** of one RAW (e.g. a plain COLOR 3 shot) with several films: the JPEGs come from identical
      pixels, which lets every look (mix, curves, split toning, Blacks / Whites) be checked exactly.
- [ ] Live ND 2f / 4f / 8f and a burst of 20+ frames on a film: no freeze, all frames saved.

## Recovery

On a computer, rename the card's `DCOLYMP` to `DCOLYMP-v1.3`, move `fallback-v1.2r2/DCOLYMP` (camera-tested v1.2-r2)
or `fallback-v1.1/DCOLYMP` to the top of the card, hold **OK** while switching on, and install.

## What to send back

Pass / fail per item; the RAW+JPEG chart shots; for anything odd, what you did just before, which film, which mode.
