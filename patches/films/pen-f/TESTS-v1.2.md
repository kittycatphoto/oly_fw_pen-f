# PEN-F films v1.2: camera test plan

Package: `DCOLYMP/E1229999.BIN`, **v1.2-r2**, SHA-256
`53773a9e0100047b2ce520bfe91a16a3bafd3c161a3ee3d5462f67f88f0039d0` (built 2026-11-25). Do not use v1.2-r1
(`52270e0d…ec79`): its hooks pointed at v1.1's function addresses and it boot-looped on the camera. It is v1.1 plus RGB curves, all 19 films regraded to caduceus-om3's current looks (24 Nov),
Whites in use, and film recognition from saturation sectors 1–8 instead of 1–4. **No Color Mix yet.** The camera
still shows firmware 3.1.

Already checked without the camera: the films code run in the emulator, bit-exact with caduceus's maths; the
startup-safety gate (the check that catches the v1 boot loop), which now also decodes every hook from the package
and requires it to reach its function (the check that catches r1's boot loop); the camera's own updater code
accepting the package. Everything below is new evidence only the camera can give.

Work top to bottom: each section assumes the ones before it passed. **Stop at the first boot problem** and go to
[Recovery](#recovery).

## On the card

| Folder | What it is |
| --- | --- |
| `DCOLYMP/` | **v1.2**, what the camera installs |
| `fallback-v1.1/DCOLYMP/` | your camera-tested v1.1 (`88cf17cc…3170`) |
| `restore-stock/DCOLYMP/` | stock 3.1 firmware (`e13f9813…f26a`) |

The camera only looks at the `DCOLYMP` folder at the top of the card.

## 1. Install and start-up (most important)

- [ ] Battery full. Card in, hold **OK** while switching on, confirm the update. It finishes and the camera restarts.
- [ ] The camera starts to live view normally (no switching itself on and off).
- [ ] Switch off and on 3 times, including once on a film (after section 2). Starts every time.
- [ ] Take a photo before choosing any film: saves and plays back normally.

## 2. Film list

- [ ] Super Control Panel → Picture Mode: the 19 films come after Color Profile 3, names readable.
- [ ] Pick a film: no freeze; the list title shows its name; reopening the list puts the cursor on it.
- [ ] **Scroll quickly** through all 19 films and back, several times (an OM-3 build once restarted from this).
- [ ] Same from Live Control (if you use it).
- [ ] Pick Color Profile 1 or 2 after a film: no film name shows; COLOR 1/2 look as before.

## 3. Recognition (changed in v1.2)

These three pairs could be confused under v1.1's rule. Pick each one and check the title shows the right name:

- [ ] Portra 800, then Fuji C200
- [ ] Ultramax 400, then CineStill 400D
- [ ] ColorPlus 200, then Astia 100F
- [ ] On a film, change one **saturation** colour among the first 8 (Color Profile editor): the name goes back to
      Color Profile 3 (expected: the film is now your own COLOR 3 look). Pick the film again to restore it.
- [ ] Switch off on a film and back on: the same film is still active.

## 4. Looks in photos

Shoot one scene with greys, skin, sky and greens (a colour chart is ideal), same light, on **Color Profile 3 with
nothing changed** and then on each film below. RAW+JPEG if possible, so we can compare later.

| # | Film | WB shift | Blacks / Whites | Split toning | RGB curves |
| ---: | --- | --- | --- | --- | --- |
| 1 | Gold 200 | A-B +1 G-M −1 | +1 / −1 | shadows Orange 1, highlights Orange 1 | yes |
| 2 | Kodachrome 64 | – | −1 / 0 | – | – |
| 3 | Portra 800 | A-B +1 G-M −1 | +1 / −1 | shadows Blue-cyan 1, highlights Yellow 1 | yes |
| 4 | CineStill 800T | A-B −1 G-M −2 | −1 / 0 | highlights Green-cyan 1 | – |
| 5 | Ektar 100 | A-B −1 | 0 / −1 | shadows Blue-cyan 1 | yes |
| 6 | Ultramax 400 | A-B −1 | +1 / 0 | – | – |
| 7 | Pro 400H | A-B −2 | −1 / 0 | – | yes |
| 8 | Velvia 50 | A-B +1 | −2 / +1 | shadows Blue-cyan 1, highlights Blue 1 | yes |
| 9 | Superia 400 | A-B +2 | +2 / 0 | – | yes |
| 10 | ColorPlus 200 | A-B +3 G-M +1 | 0 / −2 | shadows Orange-red 1 | yes |
| 11 | CineStill 400D | A-B +2 G-M −1 | −1 / 0 | highlights Cyan 1 | – |
| 12 | Fuji C200 | A-B +1 | −1 / −1 | – | yes |
| 13 | Ektachrome E100 | A-B −4 G-M −2 | +3 / 0 | shadows Blue 1 | yes |
| 14 | Reala 100 | – | 0 / 0 | – | – |
| 15 | Provia 100F | A-B −3 G-M −2 | 0 / 0 | shadows Blue-cyan 2 | yes |
| 16 | Vision3 250D | – | 0 / 0 | – | – |
| 17 | Fuji Eterna | – | −1 / 0 | – | – |
| 18 | Astia 100F | A-B +1 G-M −1 | −1 / 0 | – | – |
| 19 | Agfa Ultra 100 | – | +2 / 0 | – | – |

- [ ] Every film saves photos normally; none looks broken (posterised bands, wrong colours, black or white frames).
- [ ] Curve films (*yes* above) look different from v1.1 in tone and colour, smoothly, with no steps in gradients
      such as sky.
- [ ] **Whites −1 / −2** (Gold 200, Portra 800, Ektar 100, Fuji C200, ColorPlus 200): the brightest whites are
      slightly grey, not clipped. Whites is new on the camera.
- [ ] **Blacks +2 / +3** (Superia 400, Agfa Ultra 100, Ektachrome E100): the deepest blacks are slightly lifted.
- [ ] WB shift: set your own WB fine-tune to A-B +7, then pick Ektachrome E100 (A-B −4): the photo is less warm
      than COLOR 3 at +7. The total never passes ±7.
- [ ] Live view looks like the saved photo on 3–4 films (split toning and curves apply to live view too).

## 5. Photo paths not tested before

- [ ] **RAW Data Edit** in playback on a RAW shot with a film: the new JPEG has the film's look.
- [ ] RAW Data Edit of a photo shot on film A while the camera is now on film B: the new JPEG follows **film B**,
      the film selected at the time of the edit (found with v1.3 on 2026-11-25; this item first said film A).
- [ ] RAW+JPEG on a film: the JPEG has the look.
- [ ] **Live ND** 2f / 4f / 8f on a film: the photo saves, has the look, live view is fine.
- [ ] **Burst** (sequential H and L) on a curve film, 20+ frames: no freeze or restart, all frames saved.
- [ ] Live view on a curve film: no noticeable extra lag.

## 6. Everything else unchanged

- [ ] After using a film: Color Profile 1 / 2, Monochrome Profile, Natural / Vivid and one Art Filter look as before
      (no leftover tint or curve).
- [ ] AF Limiter and the HSL editor work as in v1.1.

## Recovery

If the camera keeps switching itself on and off, or won't start:

1. On a computer, rename the card's `DCOLYMP` to `DCOLYMP-v1.2`, then move `fallback-v1.1/DCOLYMP` to the top of
   the card (or `restore-stock/DCOLYMP` for stock firmware).
2. Card in, hold **OK** while switching on, and install. This recovered the camera after the v1 boot loop.

## What to send back

For each section: pass / fail, plus notes on anything odd (what you did just before, which film, which mode). For
section 4, the RAW+JPEG pairs of the chart scene on COLOR 3 and the curve films. If anything froze or restarted:
the exact steps, and whether it repeats.
