# A Caduceus-style firmware for the PEN-F: feasibility and roadmap

Written 2026-11-11 for PEN-F firmware 3.1 (build 3101). Question from the owner: what would it take to make a
"Caduceus" for the PEN-F, starting with films listed after Color Profile 1–3, the way
[caduceus-om3](https://github.com/androidfanman/caduceus-om3) lists them after COLOR 1–4?

This is a research and planning note. Nothing was built, written to a card or flashed. Four read-only research
passes produced the details; they are in [research/penf_caduceus/](research/penf_caduceus/README.md).

**Decided by the owner (2026-11-11):** films go in the Picture Mode list **after COLOR 3**, not on the ART/CRT
dial positions. A browser page for making films (a PEN-F Look Lab) is planned separately.

## Evidence labels

| Label | Meaning |
| --- | --- |
| **[static]** | Read from code or data in our copy of the PEN-F 3101 firmware |
| **[emu]** | Original PEN-F instructions run in the native MN103 emulator |
| **[cam]** | Tested on the owner's PEN-F |
| **[pub-cam]** | Someone else's public camera report (caduceus-om3 on an OM-3) |
| **[pub]** | Public docs or source, not re-checked |
| **[spec]** | Our inference, not checked |

Nothing in this note is **[cam]** for the Caduceus features themselves. Where the note says **[cam]**, it
refers to existing PEN-F builds (HSL, Live ND, AF Limiter), which the owner has run.

## Verdict

**Yes, a Caduceus-style PEN-F firmware is possible, built in stages.** It is a new implementation that uses
caduceus-om3 as a map. It is not a port: none of its code can be reused byte for byte.

1. **Films after Color Profile 1–3 work on the PEN-F, in a small first form.** The PEN-F builds its Picture
   Mode list the same way the OM-3 does, so caduceus-om3's trick carries over. A film value is seen only by
   the list builder, the label lookup and the setter; everything else sees an ordinary COLOR profile. That
   means no new picture modes and no changes to the 57-entry picture-mode rule maps [static, emu]. A first
   version with 4–6 built-in films after COLOR 3, each loaded onto COLOR 3, needs about 0.5–0.7 KB [static
  estimate]. The owner chose this placement on 2026-11-11.
2. **The full caduceus feature set needs more room first.** caduceus-om3 v0.24.1 used about 61 KB of code
   [pub]. The PEN-F has about 2.9 KB of free loaded space after our current build: 465 B scattered through
   sections 1–5, plus 428 B in section 6's tail (where our alignment probes 2–4 ran code on the camera, 2026-11-09 [cam]) and
   2,028 B in section 8's untouched tail [static]. caduceus-om3 got
   its room by moving a section's loaded-end word, which was proven on an OM-3 [pub-cam]. The PEN-F has the same
   mechanism: section 5's end word at `0x60042105` sits in front of a 206 KiB empty stretch, and the stock
   loader copies an extended section in the emulator [static, emu]. One small camera probe decides it.
3. **The platform pieces exist.** These were found on the PEN-F [static]:
   - card file functions (open, read, write, seek, close);
   - the heap allocator;
   - a way to call the file system from any task;
   - the settings facade;
   - a half-press method that can be hooked by swapping one vtable word.

   Two pieces are still missing: a "card is ready" flag and a proven spare RAM word.
4. **The look itself:**
   - **Stock settings cover a usable film look today:** the 18 COLOR-profile settings plus fishcu's HSL
     (hue and luminance per colour, already [cam]).
   - **Extras that need new hooks:** Blacks/Whites, split toning, per-film noise filter, sharpness, lens
     vignette correction and WB shift [static].
   - **Colour grain is the hardest.** PEN-F grain runs as its own pass and turns the photo grey, unlike the
     OM-3's [emu].

## 1. What Caduceus is today (caduceus-om3 v0.26.2) [pub]

Read from its repository through the GitHub API and our local copy of v0.24.1. Upstream moved from v0.24.1 to
v0.26.2 between 2026-11-08 and 2026-11-09, and v0.27 is in progress.

- **Films in the Picture Mode list:** FILM 1–20 after COLOR 1–4, five per COLOR, with names. Picking a film
  loads its settings onto that COLOR. Edits are kept per film in `EDITS.BIN`, `*` marks a changed film, and
  holding OK resets it.
- **Picture Mode rows** on the camera's own screen: Blacks, Whites, WB shift A-B/G-M (±7), Sharp (−5 Off..+2),
  Noise Filter (with a new High), lens vignette correction, and Film Grain.
- **Hue and Luminance** pages on the colour wheel.
- **Fast colour grain** through the image processor (v0.25, borrowing the Grainy Film Art Filter's texture
  route), plus Glow/Clarity.
- **Split toning:** Shadows and Highlights pages (v0.26).
- **Loading and stepping:** films load at power-on, and the Super Control Panel dials step through them
  (v0.26.2).
- **v0.27 (test build):** each creative-dial position can load a COLOR or a film.
- **Control Panel:** a browser editor that makes the card files (`LOOKS.BIN` and others), with 60 film sims.
- **Built on:** card files with magic, length and CRC, written `.NEW` → `.BAK` → `.BIN`. A code block is loaded
  from `GUIDES.BIN`, and the code uses a camera-proven 64 KiB section extension.

caduceus-ep7 (E-P7) adds Mono film presets, halation, XPan/21:9, button functions and a video colour profile
([PARITY.md](https://github.com/androidfanman/caduceus-om3/blob/main/docs/PARITY.md)) [pub].

## 2. Feature by feature on the PEN-F

**Status words:**
- **Have** = already on the owner's PEN-F;
- **Stock** = a stock PEN-F setting that a film can simply write;
- **Hook** = needs new code at a known site;
- **Research** = the site or route is not settled;
- **Later** or **Skip**.

| Feature | PEN-F status | Route | Evidence |
| --- | --- | --- | --- |
| Hue / Luminance per colour (12) | **Have** | fishcu's HSL release: hook after the COLOR builder at `0x604f7506` | [cam] |
| Saturation ×12, Highlights/Shadows/Midtones, Contrast, Sharpness ±2, Shading | **Stock**, per COLOR profile | 18 stored ids per profile: COLOR 3 = 918, 915, 973–975, 1113, 955–966 (COLOR 1/2 analogous) | [static] |
| Films after Color Profile 1–3 | **Hook**, small first form | Section 3 below | [static, emu] |
| Film names on screen | **Hook** | Label lookup `0x60c8972a` takes a text record ("FILM 1" shown natively); new bitmaps are impractical, so films reuse COLOR 3's icon | [emu] |
| Changes kept per film, `*`, hold-OK reset | **Hook**, needs card files | No stock "COLOR changed?" GUI to borrow; written for the PEN-F | [static] |
| Noise Filter per film (incl. High) | **Hook** | Stock but global (High already exists); override the getter at `0x60253657` (capture) and `0x60af3e99` (RAW edit) | [static] |
| Lens vignette correction off per film | **Hook** | Global setting 61; five reads of key `0x8c21` | [static] |
| Sharp down to Off | **Hook** | Stock lowest gain is 64 of 256, not 0; a true Off needs a change in `0x604f3ba1` | [static] |
| WB shift per film | **Hook** | Global, per WB preset, ±7; about 9 getter sites, live view at `0x6055741c`/`0x60557431` | [static] |
| Blacks / Whites, highlight roll-off | **Hook** | Tone step after the luminance-LUT builder: site `0x604f85ef` (`mov d3,a0; call 0x604f7d50,…,76`), LUT built by `0x604f7c76`; about 0.5 KB | [static] |
| Split toning | **Hook** | PEN-F Cross Process already uses three R/G/B curves; selector `0x604f2a94`, call `0x604f60d2`; about 150 B plus 1.5 KB of curve buffers | [emu] |
| Colour film grain | **Research** | MONO grain is a separate pass here and the MONO key turns the photo grey; routes: COLOR key + four overrides, or Grainy Film's texture pass (`0x604d8982`) without its grey pass; no Low/Med/High mapped | [emu, spec] |
| Glow / Clarity, Art Effects on COLOR | **Research** | Art Effect id key `0xf5d1` (read at `0x60253b16`), converters `0x60524f8a` / `0x605356e2`; the strength site is not found | [static] |
| Mono film presets (E-P7 style) | **Stock + Hook** | MONO 1–3 already have colour filter, toning and grain; the same list trick after MONO 1–3 | [static, spec] |
| Films on the ART / CRT dial positions | **Hook**, cheapest | Section 3.3 | [static] |
| Film recipe in EXIF | **Later** | We already write EXIF 0x101c from H6, so the writer is known | [cam for 0x101c] |
| Live ND, AF Limiter | **Have** | Our builds | [cam] |
| Panasonic aperture ring | **Upstream research** | Documented on the PEN-F in this repository (`19a514d`) | — |
| XPan / 21:9, button functions | **Later** | caduceus-ep7 has them; not studied for the PEN-F | — |
| Video colour profile, 10-bit | **Skip** | The owner does not use video | — |

## 3. Films after Color Profile 1–3: how it works on the PEN-F

### 3.1 The stock list [static, emu]

- **The cell:** the SCP / Live Control Picture Mode cell is setting **906**. In the per-setting builder table at
  `0x60f489c0`, 906 maps to list builder **`0x60c7f779`**. With 906 = 910 (COLOR family), the builder lists
  setting **910**, the counterpart of caduceus-om3's setting 901.
- **Setting 910** combines raw value 11 and profile setting 1086, and its value table is {1, 54, 55, 56}.
  Picking 55 sets 1086 = 2 and picture mode 55 (COLOR 2).
- **COLOR records:** the table is at **`0x60f491f8`** and holds three 12-byte records: {54, 1048, `0x60c7eac4`},
  {55, 1049, 0}, {56, 1050, 0}. Its address is the immediate at `0x60c7f7f4`, and the count is the byte in
  `mov 3,a3` at `0x60c7f7fb`.
- **Running the builder natively** gives [54, 55, 56]. Setting 1050 = 0 drops COLOR 3. The cursor comes from
  GetValue(910), whose call returns to `0x60c7f898` [emu].
- **The facade** is the vtable at `0x609a4660` in ROM: setter slot 0 (`0x607363b3`), getter slot 2
  (`0x607359ef`), selectable slot 9. It matches the OM-3 facade slot for slot, offset by one slot. Wrappers are
  installed by changing the vtable words, as data only.
- **Labels:** the label array is at `0x60f59a28` (strings 2749–2751, "Color Profile 1–3"). The icons are
  bitmaps 4350–4352 (`0x60f58fc0`) and 4344–4346 (`0x60f59680`). The lookup routine `0x60c8972a` writes
  nothing when a value is missing, so the old label stays [emu].

### 3.2 First version: N built-in films on COLOR 3

1. **List:** a new record table with COLOR 1–3 followed by N film records. Repoint the 4-byte table address,
   and change the 1-byte count in the builder.
2. **Facade wrappers:** for setting 910 only, a selectable wrapper accepts film values, and a setter wrapper
   turns a film value into COLOR 3 and runs the film loader. A getter wrapper (optional) puts the cursor on
   the film.
3. **Film loader:** writes the film's 18 COLOR 3 values and its 12 HSL words through the stock setters. HSL's
   own Wi-Fi recipe path already writes settings at run time this way [static, pub-cam by fishcu].
4. **Labels:** a 5-byte hook in `0x60c8972a` gives each film a text label.
5. **Size:** about 250–300 B of code and 200–400 B of data [static estimate].
6. **Placement:** this does not fit the 465 B left in sections 1–5. It needs either the untouched section-8
   tail (2,028 B; loaded at boot but never yet used by our code) or the section-5 extension (phase 1).

**Costs of this first form:**
- picking a film overwrites COLOR 3's own settings;
- the SCP cell and shooting screen still say COLOR 3;
- edits are not kept per film;
- the chosen film is not remembered over power-off, unless we use a spare setting (399/400 are candidates, not
  checked).

### 3.2a How many films fit (2026-11-11, owner's 20-film list)

All sizes are [static] estimates; nothing is assembled yet.

**Per film**, packed:

| Part | Size |
| --- | --- |
| 42 values (hue, light and saturation ×12, contrast, sharpness, shading, tone ×3), each fitting in 4 bits | 21 B |
| WB shift A-B and G-M | 1 B |
| ASCII name, up to 15 characters plus NUL (expanded to the label format at run time) | 16 B |
| List record | 12 B |
| **Total** | **≈ 50 B** |

Unpacked (one byte per value, UTF-16 names) it would be about 90 B.

**Fixed code:** list, facade wrappers, loader and labels, about 300 B, plus about 40 B for name expansion.

**Where it can go:** sections 1–5 have no hole bigger than 76 B, so neither the code nor the film table fits
there. Section 6's tail (428 B) fits the code but only a couple of films. Section 8's tail is one block: 2,028 B
in all, or 1,888 B inside fishcu's margins.

| Space | Films that fit | Status |
| --- | --- | --- |
| Holes in sections 1–5 (465 B, max 76 B each) | 0 | — |
| Section-8 tail (1,888 B) | **all 20**: 340 + 20 × 50 ≈ 1,340 B, about 550 B spare | Loaded at boot, never yet used by our code; the first camera test of it is itself the proof |
| Section-5 extension after PX1/PX2 (4–64 KiB) | Hundreds; the limit becomes the list screen and the card | Needs phase 1 |

**The owner's list:** entry 1 "Look 1" is caduceus's empty custom slot, not a film. On the PEN-F, COLOR 1–3
themselves stay the custom slots, so v1 has **19 films** (entries 2–20). Portra 400, the film in that place on
the live page, can be a 20th if wanted.

**Two caveats for v1** (film data: caduceus-om3 v0.26.2 `webapp/src/data/om3films.json`, fetched with the
owner's OK on 2026-11-11; all 20 films are in it):
1. **Most films use a phase-5 setting** [pub data, our count]:
   - 10 of the 19 use a WB shift;
   - 10 use split toning;
   - only **Ektar 100, Reala 100 and Astia 100F** use neither.

   All HSL values are within ±5, so they fit the PEN-F's ±7. v1 ships the other 16 without those parts, so they
   look different from the OM-3 versions until phase 5. For WB shift there is a v1 option: the loader also writes
   the stock WB fine-tune for the current WB mode. That's cheap, but it changes your own WB shift and leaves it
   changed after you leave the film. Split toning has no stock setting to borrow.

   Recommended: ship v1 without both, and label it "v1 colours" in the film list notes.
2. **Per film,** WB and split add about 3 B once phase 5 lands (≈ 53 B per film), which still fits.

**Open:** whether the SCP and Live Control list screens scroll through 22 entries (COLOR 1–3 + 19). The
builder's count is a byte, so the code allows it; the screen is checked in the emulator, then on the camera.

**Decided by the owner (2026-11-11, revised the same day): section-8 tail, no probe.** The owner first chose
the space probe. After the brick-risk check, they changed to this. That check found that the SD updater
(task 95, `0x60b1cbb5`) lives in section 5 and runs only after the loader step PX1 changes, so a bad PX1 could
block its own recovery [static].

v1 goes in the section-8 tail (code and data) and the section-6 tail (the WB stub). No loader or end-word
change, so the risk is the same runtime-only kind as every earlier build. PX1/PX2 are shelved until there is
more confidence about recovery (phase 1).

#### Compared: COLOR 3 list vs ART/CRT dial vs dropping the AF Limiter

| | List after COLOR 3 (chosen) | ART / CRT dial positions |
| --- | --- | --- |
| Fixed code | ≈ 340 B | ≈ 120–150 B, plus the same loader core (≈ 100 B) |
| Per film | ≈ 50 B | ≈ 40 B (no list record) |
| Films possible | Section-8 tail: **20**; after the extension: dozens | **2**, one per dial position, whatever the space |
| Can ART/CRT hold more? | — | Not without a picker, and a picker is the COLOR 3 list code again. Their ~52 stored setting ids are settings storage, not code space: they don't make room for more film definitions. They could keep about 2 films' own edits without a card file |
| What it costs you | Picking a film overwrites COLOR 3's settings (approved for v1; phase 4 removes it) | ART and CRT disappear from the dial; COLOR 3 is untouched |

**Dropping the AF Limiter** from `hsl-8f-afl-ovl` frees two separate pieces [static, from `probes/aflimit2.py`]:
- helper H7 at `0x60fdc7c0..0x60fdc7f3`, which leaves about 64 B free at the end of section 5;
- the row labels at `0x60427fac..0x60427ffd`, which leaves about 88 B free at the end of section 2.

That is about 150 B in two blocks. The rest of the AF Limiter is in-place edits that free nothing. Neither block
holds the fixed code. At most they would hold 2–3 extra film records, which isn't needed when the section-8 tail
holds all 20. For ART/CRT it changes nothing (still 2 films).

**Recommendation:**
- **Keep the list after COLOR 3 and keep the AF Limiter.** The list holds the whole 19-film set in space
  available today, while ART/CRT caps at 2 films however much space there is.
- **Storage isn't the limit; code space is.** Taking ART/CRT's storage wouldn't let more films fit.

### 3.2b White balance in v1 (owner, 2026-11-11: required)

The owner said "a big part about film sims is white-balance", so v1 ships with each film's WB shift. Two ways
were compared.

**(a) Per-film WB shift hook, pulled forward from phase 5 (chosen).**
- **How it works:** stock WB compensation is two global key arrays, `0x84f9` (A-B) and `0x9679` (G-M). Each
  has about 20 entries, one per WB preset, ±7. The camera reads them through the getter `0x600750ee` at
  about 9 call sites [static]:
  - capture: the WB-mode switch `0x6054f1dd..0x6054f540`, five pairs, stored into capture +18640 / +18642;
  - live view: `0x6055741c` / `0x60557431`;
  - `0x60567dcc` / `0x60567de4`;
  - RAW edit: `0x60af5513` / `0x60af5527`.
- **The change:** each site's 7-byte `call` goes to a stub that runs the real getter, then adds the film's
  shift and clamps to ±7. It does this only when the key is A-B or G-M, a film is active and the effective
  picture mode is COLOR 3 (public mode 56). This is the same additive design as caduceus-om3's `wb_get`
  [pub], which covers every WB mode, Auto WB included.
- **Your own WB untouched:** your own WB mode and fine-tune settings are never written. Leaving the film (or
  picking COLOR 1–3) gives the stock value back immediately.
- **Travels with each shot:** the capture copies the shifted value into the capture record (+18640 / +18642),
  so the shift goes with each shot through every development path. That is the per-capture rule from phase 5,
  met by the stock code.
- **"Film active"** is the film number kept in a spare setting. It survives power-off, since COLOR 3 still
  holds the film. Candidate settings are 399/400, to be checked (3.4 item 5). The film list needs this setting
  anyway.
- **Bytes:**
  - 95 B for the stub;
  - 16 × 4-byte call-displacement edits in place (no space needed);
  - 1 B per film (A-B and G-M as nibbles; already counted in the ≈ 50 B per film in 3.2a).

  The total with 19 films is about 1.45 KB, well inside PX1's 4 KiB.
- **Evidence:** [emu], from the R-WB pass on 2026-11-11 (`research/penf_caduceus/05_RWB_EMULATOR.md`):
  - there are **16 sites** (8 pairs), all `call 0x600750ee,[d2,d3],12`;
  - a 95-byte stub passed 80 decision cases;
  - running stock code at the capture, live-view and RAW-edit sites gives stock + shift, clamped.

  Film-state setting: **597**, not 598 (changed during the v1 build on 2026-11-11). 598 turned out to be a
  type-6 compound setting, which can't hold a number. 597 is the hidden E-M1 [HDR]+[BKT] button option: a
  plain byte with its own store key `0xe8c1`, and its readers only test `== 1` [static]. It holds film j + 2,
  with its list widened to 0..20, and the rules engine allows 0..20 with nothing forced [emu].
- **Risk:** low to medium. A wrong site means a wrong colour, not a crash. The colour itself needs a camera test.
- **RAW edit caveat:** in-camera RAW edit reads the current setting, so it uses the film active at edit time,
  as stock RAW edit uses current settings [spec].

**(b) Write the film's shift into the global WB fine-tune (not chosen).**
- **Restore problem:** the loader would write the film's A-B / G-M into the current WB preset's entries.
  Restoring your value on leaving needs the old value saved somewhere that survives power-off. Spare settings
  would be needed for 2 values plus a flag per preset; covering a change of WB mode on the film means about 40
  values.
- **Conflicts:**
  - if you change your fine-tune while on a film, the restore overwrites your change;
  - if you switch WB mode on a film, the shift doesn't follow, unless every preset is written.
- **Visible changes:** your WB menu shows the film's numbers while you're on it.
- **Bytes:** about 120–200 B of code plus the saved values. That is no smaller than (a), with worse behaviour.

**Recommendation and P2 scope:** (a). v1 = the 19 films after COLOR 3, each with its 18 COLOR values, 12 + 12
HSL words, name and **WB shift (option a)**.

**Split toning** stays in phase 5. It changes the development pipeline itself:
- the selector hook `0x604f60d2`;
- about 1.5 KB of curve buffers per development context;
- per-capture transport of the film's tint, since the development job doesn't know which film was active
  when the shot was taken.

That is pixel-level work, which the emulator can't check, unlike WB's stock capture-time copy. It is the first
item after v1 (phase 5, first). It affects 10 of the 19 films.

**Research item R-WB: done 2026-11-11** (see Evidence above; one open item, the state setting). The plan
it followed:
1. Disassemble the 9 sites and record each one's call shape, frame and key / index registers.
2. Run the capture WB switch natively for several WB modes, Auto included, with a model stub, and check that
   capture +18640 / +18642 get stock value + film shift, clamped.
3. Confirm that the live-view pair drives the preview.
4. Confirm that 399/400 (or another spare id) is unused.

### 3.3 Not chosen: films on the ART and CRT dial positions [static]

The owner chose the list after COLOR 3 (2026-11-11). This route is kept for reference, and as a possible
add-on in phase 8. About 120–150 B, with no list work:
1. In the dial → 906 writer, change the ART and CRT constants (at `0x60ba4e5b` and `0x60ba4e73`) from 908/909
   to 910.
2. A stub on the shared write at `0x60ba4e99` records "film A / film B / none" from the dial position.
3. A read redirect in the bank getter `0x602bc3ca` serves the film's values for the loader's COLOR 3 case, so
   COLOR 3 itself is never touched.

Remapping the dial table `0x609554dc` instead would hide the dial change from `0x60b9b1da`, and nothing would
refresh. The film-loader core is the same as in 3.2. The cost is that ART and CRT leave the dial, and you get
only two films. caduceus-om3 is building the same idea for v0.27 [pub-cam on its test build].

### 3.4 Open questions before building

1. Where the SCP grid, Live Control and shooting-screen readouts call GetValue(910). Next step: an emulator
   trace of the facade's return addresses.
2. Whether the stock rules refuse selectable(910, film value).
3. The exact commit handler for the 906 list (pointer `0x60c844e5`).
4. Whether turning a dial on the SCP cell steps through the settings engine and skips films. caduceus-om3
   needed a separate change for this in v0.26.2.
5. Whether settings 399/400 are really unused.
6. How long 18 setter round-trips take for one film load.
7. That fishcu's HSL bytes do not overlap `0x602bc3ca` or any site we choose.

## 4. Platform: code space, card files, storage [static unless noted]

### 4.1 Free code space after the current camera build (`hsl-8f-afl-ovl`)

| Section | Loaded range | Free (holes ≥ 4 B) |
| --- | --- | --- |
| 1 | `0x60142800..0x601cb000` | 177 B |
| 2 | `0x6022a800..0x60428000` | 95 B |
| 3 | `0x60432800..0x6069b800` | 76 B |
| 4 | `0x606b4800..0x60a50000` | 23 B |
| 5 | `0x60a76000..0x60fdc800` | 94 B |
| 6 | `0x61010000..0x610f2000` | 428 B at `0x610f1e54`; unused by the current build. Alignment probes 2–4 ran code at `0x610f1ea0` on the camera [cam] |
| 8 | `0x61104000..0x6115b800` | 2,028 B at `0x6115b014`, untouched |

The section table is at `0x60026d7c` (8 entries), the loader at `0x600421e1`, and the end selector at
`0x600420c1`. All eight sections load at every boot, in order. Our 8f helpers are inside loaded tails, as
their camera results require [cam].

### 4.2 Section-5 extension (the room for everything after the first version)

- **End word:** section 5's end is the imm32 at **`0x60042105`** (`0x60fdc800`). It is followed by
  `0x60fdc800..0x61010000`: 206 KiB, all `FF`, inside the main component. The container doesn't grow.
- **No other references:** the end word is the only reference into that stretch [static].
- **Emulator:** with only the end word changed (+4 KiB or +64 KiB), the stock loader copies the extension
  exactly [emu]. Flash is modelled, so this proves the loader logic only.
- **Avoid sections 1, 7 and 8:**
  - data sits after sections 1 and 8;
  - section 8's end also bounds a load-time bus guard;
  - section 7 is loaded by the second CPU's path.
- **Probe PX1** (mirrors caduceus-om3's GX1, not built):
  1. +4 KiB, with a magic word, a small probe routine and a test pattern at `0x60fdc800`.
  2. The EXIF frame-count helper H6 moves into section 5's margin and gains a magic check. A 2f shot then
     records "loaded and intact" or "bad" in EXIF tag 0x101c. No file I/O is needed.
  3. PX2 repeats the test at +64 KiB.

  The build's loader check must use the new end.

### 4.3 Card files

| Piece | PEN-F | OM-3 [pub] |
| --- | --- | --- |
| fopen / fclose | `0x60599595` / `0x6059959e` (9 B apart, as on OM-3) | `0x608d4d22` / `0x608d4d2b` |
| fwrite / fread | `0x60599615` / `0x60599715` | `0x608d4da9` / `0x608d4eb7` |
| ftell / fseek | `0x6059979e` / `0x60599804` (whence 2 SET, 0 CUR, 1 END) | same map |
| mkdir | probably `0x605999d1` | — |
| malloc / free | `0x60023459` / `0x60023498` (pools ≤128 / ≤2048 / ≤16384 B) | `0x60024068` / `0x6002409a` |
| Cross-task call | `0x6059c8db` forwards to the file-system task and waits; task id `0x60031be2` | gate on the HLS task |
| Half-press | method `0x60baffba` (press-1st in still shooting), vtable words at `0x60db3810` / `0x60dbd384`; the task that runs it is unknown | `0x60415216` |
| Card ready | **not found** | media word |
| Spare RAM word | **none proven**; a word in our own cave is reset at boot, and whether code space is writable is untested | `0x62b4dd16` |

The drive is `C:`. caduceus-om3 keeps 5–20 films with per-film edits in card files, and the PEN-F should do
the same. The only stock storage that could be reused is the 52 or so ART/CRT ids, enough for one extra
look [static].

## 5. Roadmap

Each phase ends with something the owner can test on the camera, or with a decision. Every build follows the
existing order: static map → emulator checks → build with full preflight → **write only when the owner says
"write"** → **copy only when they say "copy"** → the owner flashes and tests → result recorded. The restore
files stay as they are today.

### Phase 0: Decisions (owner, no build)

1. **First form of films: decided** (2026-11-11): the list after COLOR 3 (3.2).
2. **COLOR 3 as the film slot: approved** (2026-11-11): a film may overwrite COLOR 3 in the first version.
3. **Which films: decided** (2026-11-11): the owner's 20-entry list (section 3.2a), which is 19 films plus
   caduceus's custom slot. Space: section-8 tail, no probe (decided 2026-11-11). WB shift in v1: required by the owner, option (a) (3.2b). The current film values were fetched
   (v0.26.2) with the owner's OK. caduceus-om3's looks are Apache-2.0 data and can be used with credit [pub]. Their hue
   direction and ±5 range would be translated to the PEN-F's HSL, where H = −1000 × slider as on the OM-3 and
   the range is ±7 [pub-cam on both cameras]. Alternatively, the owner picks their own looks.

### Phase 1: Prove code space (space probe PX1, then PX2) — SHELVED 2026-11-11

Shelved by the owner until recovery is better understood: the SD updater runs from section 5, after the
changed loader step. The probe stays built and preflighted (PX1 `da437bb6…7f69`, never written). It comes
back when later phases outgrow the section-6 and section-8 tails.

The probe is built on `hsl-8f-afl-ovl` by the private `probes/space_probe_build.py` (`space_probe.s` /
`.ld`). `--size 4` gives PX1, `--size 64` gives PX2.

**What changes:**
1. Section 5's end word (imm32 at `0x60042105`) goes from `0x60fdc800` to `+4 KiB` / `+64 KiB`. The loader
   `0x600421e1` copies `end − dest` bytes, and only it calls the end selector with 5 [static].
2. The extension holds a head magic, a word count, a checksum, the routine `px_check`, a pseudo-random
   pattern, and a tail magic.
3. `px_h6` replaces Live ND's EXIF helper H6. It lives in section 6's tail, which is camera-proven.

**The report:** `px_h6` keeps H6's work and adds `1000 × code` to the frame count in EXIF tag 0x101c. A 2f
shot therefore reads 2 when the extension isn't loaded, **1002** when it loaded and its code ran over an intact
pattern, 2002 for a bad pattern, and 3002 when it is partly loaded.

**Emulator results** [emu]:
- **Report:** all nine cases give the expected value: stock H6, loaded at 2f/4f/8f, extension FF or garbage,
  one word changed, tail missing. The callee-saved registers and the stack are intact.
- **Loader:** with the extended end, the loader copies section 5 plus the extension exactly. The base build's
  loader leaves the extension RAM untouched. Sections 2 and 6 load exactly.
- **Cost per Multiple Exposure shot:** about 5,000 instructions for PX1 and 82,000 for PX2, well under a
  millisecond [spec, from the step count].

**Camera (owner):** see `TEST_PLAN_SPACE_PROBE.md` in the private project folder. In short:
1. Shoot 2f right after power-on.
2. Use the camera normally (photos, playback, a short video, menus).
3. Shoot 2f again, then after a power cycle.
4. Read tag 0x101c on each 2f shot.

**Done when:** PX2 reads 1002 on every check. All later code then goes from `0x60fdc800`, above section 5's
stock end.

**Not tested by this probe:** writing to the extension at run time. Phase 4's state word can live in the heap
instead.

**Risk:** a change to the boot-time loader. If the camera doesn't start, the recovery path from a camera that
won't start has never been tested on the PEN-F. The normal restore is today's `hsl-8f-afl-ovl`.

### Phase 2: Films after Color Profile 1–3, first version

- **Research before the build, alongside phase 1:** R-WB (3.2b) and the open questions in 3.4, all in the
  emulator.

- **Start:** settle the open questions in 3.4 in the emulator (trace, selectable check, builder and label
  lookup with N films, loader through to the effective settings).
- **Build:** the owner's 19 films after COLOR 3, each loaded onto COLOR 3, with text labels and **each
  film's WB shift** through the per-film WB hook (sizes and placement in 3.2a, WB in 3.2b). The film table is
  generated from a looks JSON exported by the Look Lab page (first stage, planned separately), or written
  by hand if the page isn't ready.
- **Camera (owner):**
  - the list in the SCP and Live Control;
  - photos with each film;
  - power cycle;
  - C1–C4 recall;
  - menu Reset;
  - a shot right after switching films.
- **Done when:** each film shows in the list with its name and gives its look in live view and in the JPEG.
- **Size:** 1,625 B in the section-8 tail (491 B code, 22 list records, 19 labels and names, 19 × 21 B values)
  plus 116 B in the section-6 tail (the WB stub and table).

**CAMERA RESULT 2026-11-11: boot loop.** Recovered (owner). Likely cause [static]: v1's code sat in the section-6
and section-8 tails, but always-used shared code (facade vtable, label lookup, WB getters) pointed at it, and
sections 6–8 load only after sections 1–5 and their users are running. Details, the ranking of other
candidates, and the new **startup-safety gate**: `research/penf_caduceus/08_STARTUP_SAFETY.md`. **Recovery confirmed by the owner:** reflashed `hsl-8f-afl-ovl` with OK held at power-on. This is the first
proven recovery of a PEN-F that wouldn't start, for a crash after the updater path.

**v1-r2 built 2026-11-11:**
- every new byte is in section 5's reclaimed `osd` handler (1,741 B, leaving 4,232 B for v1.1);
- startup gate: clean PASS with no waivers;
- the `osd` region is reached only from the 3 hidden-shell table words, which now hit a `clr d0; rets` stub;
- v1 emulator suite and offline preflight pass, package `a7bb89bd…f22b`;
- not written; the test plan starts with 5 power-on cycles.

**v1-r2 camera result 2026-11-11:**
- startup fine (5 starts), so the section-5 placement fixed the boot loop;
- moving the Picture Mode cursor onto a film froze the camera. The power switch didn't respond until the battery
  came out.

Likely cause [static]: the H/L load used HSL's Wi-Fi route `stock_app_event` (`0x60aa4e7b`), which loops
waiting for a reply meant for the Wi-Fi worker, called from the GUI task. The list applies the value under the
cursor, so no OK was needed.

**v1-r3 built:**
- H/L go through the stock facade setter, with HSL's axis byte set so its camera-proven hook writes the cells;
- no app events;
- the hook site was run natively [emu];
- gate clean, preflight passed, package `dfda4d9b…ca93`, not written.

**v1-r3 camera result 2026-11-11:**
- films can be selected, with a short pause per step;
- the Gold 200 photo matches saturation, contrast, sharpness, Highlights and, decoded from the ORF's CMIO
  coefficients, hue and luminance;
- no WB shift, and the list cursor stayed on COLOR 3: the setting-597 write doesn't stick;
- film entries show blank.

**v1-r4 built:**
- the active film is recognised from COLOR 3's saturation, sectors 1–4, unique across the 19 films;
- 597 dropped;
- for film values, the label table gives the name and other picture tables give COLOR 3's entry;
- a frame-size bug was caught in the emulator before the camera;
- gate clean, preflight passed, package `f4673847…f369`, not written.

**v1-r4 camera result 2026-11-11:**
- startup fine;
- a picked film stays selected over power cycles;
- the list cursor still returns to COLOR 3 (deferred);
- film entries read "Color 3": the selection screen reads a different text table;
- the WB tags were identical on COLOR 2 and Gold 200 shots, which is inconclusive until a manual-A+4 calibration
  shot.

**v1-r5 built:**
- `fl_lk` gives the film name for any text table (value 56's entry has type 4) and COLOR 3's entry otherwise;
- gate clean, preflight passed, package `5a5716ac…c033`, not written.
The space-option reasoning in 3.2a that preferred the section-8 tail is superseded by this.

**v1-r5 camera result 2026-11-12:** film names show in the strip's title bar; the film WB shift still missing.

**v1-r6 (diagnostic) camera result 2026-11-12:** COLOR 3's title read the raw recognition bytes. setting_get(111)
returns **11** (the COLOR family code) on COLOR 3, not 56, so the recognition's mode test never passed [cam].

**v1-r7 camera result 2026-11-12: pass.** COLOR 3 is now 111 == 56, or 111 == 11 with profile setting 1086 == 3.
The list cursor opens on the active film, and the film WB shift reaches the capture: `WhiteBalanceBracket` reads
the owner's fine-tune plus the film's (Gold 200 warmer, CineStill 800T cooler) [cam].

**v1-r8 (clean-up): CAMERA PASS 2026-11-13.** r7 without the diagnostic; COLOR 3 keeps the name "Color 3" and only
the film entries carry film names. The owner reports it "works good" [cam]. **Phase 2 (films v1) is done**:
19 films after COLOR 3 with names, cursor, look and WB shift, coexisting with HSL, Live ND and the AF Limiter.

**Built 2026-11-11** (private `probes/penf_films_build.py`, `penf_films.s`, checks in `penf_films_checks.py`;
not written; camera test plan `TEST_PLAN_FILMS_V1.md` in the private project):
- **List:** the COLOR record table is repointed with count 22; facade slots 0 / 2 / 9 are wrapped, and slot 2
  chains to HSL's `hsl_get`; the label lookup entry is hooked.
- **Loading a film:** writes 19 settings through the stock facade setter (saturation ×12, contrast, sharpness,
  tones H/M/S, film state 597, then 910 → COLOR 3) and posts its 24 H/L cells through HSL's recipe receiver
  (event `0x041b0011`). HSL's editor axis byte is held at S while the film loads.
- **Film state:** setting **597** (hidden [HDR]+[BKT]; readers only test == 1), with its value list widened to
  0..20 (stock list `0x603df6a7`) and holding j + 2.
- **Emulator results:**
  - stock list builder: 22 entries, cursor on the active film;
  - film load sequences for films 1 / 5 / 19, COLOR picks clearing the state, other ids untouched;
  - all 19 films' posts accepted by HSL's own validator;
  - labels give the film names, and the icons are COLOR 3's;
  - WB decisions for every film;
  - stock rules engine: 597 = 0..20 allowed, nothing forced;
  - sections 6 and 8 load exactly.
- **Not covered by the emulator:**
  - the screens themselves;
  - turning the SCP dial on the cell (may skip films);
  - the app-event path running in the real application task;
  - how long a film load takes;
  - the colour result.
- **What v1 drops from caduceus's films:** split toning (10 of 19 films), Blacks / Whites, and grain / glow
  (none of the 19 use them).

### Phase 2.1 (v1.1): split toning and Blacks / Whites (owner, 2026-11-11)

The owner's plan: test v1 first; if it works, add split toning and Blacks / Whites as v1.1. They are kept out
of v1 so that a camera failure in v1 stays easy to trace. Research notes:
`research/penf_caduceus/06_TONE_SPLIT.md` (hooks, transport, sizes) and `07_RECLAIM.md` (space).

**Hooks** [static, emulator for the LUT and curve formats]. These correct the earlier notes:
- **Blacks / Whites:**
  - Hook the **LUT builder call `0x604f85e8`** (7 B), not the step after it. The builder only rebuilds when
    C+56 & `0x2e8063e`, so remapping in place would keep the previous film's curve.
  - The stub sets the rebuild bit for COLOR, runs the stock builder, restores C+56, then copies the LUT into
    the job buffer O+0x1234 and remaps it.
  - The LUT is 256 × u16 on a 10-bit scale, the same as the OM-3, so caduceus's remap maths carries over.
- **Split toning:**
  - The RGB curves are packed `R | G<<10 | B<<20` in a 256 × u32 job table, O+0x424 / O+0x824, filled by the
    copier `0x604f5f7b` / `0x604f5ff1`. Hook after the copier at **`0x604f62dc`** (6 B).
  - The stub bends the table in place, using caduceus's per-colour K table, and sets C+100 |= 3 so the table is
    re-uploaded. No extra buffer is needed.
  - The earlier "selector `0x604f2a94`, O+0x1430" note was wrong.
- **Per-shot transport:**
  - Patch the entries of fishcu's shared `hl_source_to_owner` (capture, live view and RAW-edit acquire) and
    `hl_owner_to_job` (preview, live view and the saved JPEG) to carry a film row into a new job field at
    +14944.
  - That grows the job from 14944 to 14948 B with two data edits (`0x604c1c0f`, `0x604c1d1f`); it stays in its
    16 KiB heap class.
  - The acquire sites read setting 597 through the key getter `0x600750ee`, as stock does there. The
    development hooks never read settings. That keeps RAW+JPEG second developments and RAW edits correct.

**Size:**

| Part | Code + data | Site / data edits |
| --- | ---: | ---: |
| Blacks / Whites | ≈ 281 B + 1 B per film | |
| Split toning | ≈ 272 B + 36 B table + 2 B per film | |
| Transport | ≈ 242 B + 45 B row table | |
| **Both, with transport** | **≈ 933 B** | **+28 B** |

The sizes come from a sketch that assembles but has not been run.

**Space:** v1 leaves 263 B in the section-8 tail and 172 B in section 6, which is not enough. The space
research found debug-shell command handlers in **section 5** that only the hidden RTOS shell's command tables
reach [static]:
- `osd` at `0x60a79cdc..0x60a7b434`: 5,976 B;
- `spc`: 3,264 B;
- `efct`: 2,987 B.

The SD updater and the boot path can't reach them. Stubbing the handler's first 3 bytes (`clr d0; rets`)
frees the rest, with **no loader change**. v1.1 would use `osd`. Section 5 also suits pipeline code.

**Before v1.1:**
1. An emulator execute-watch confirms the section-5 constructors and the boot to live view never run the
   `osd` range.
2. Emulator checks of the builder gating, the remap and bent tables, and the transport copies.
3. The camera checks the colour result, live-view cost, and RAW+JPEG.


### v1.1a: Blacks / Whites, built 2026-11-13 (not written)

v1.1 is split in two camera rounds so that a failure stays easy to trace: **v1.1a = Blacks / Whites**,
**v1.1b = split toning**. The split colour table lives in caduceus-om3 v0.26 (`model.py` and the firmware's split
routine), which our local copy (v0.24.1) does not have; v1.1b needs the owner's OK to fetch it.

**Design change from the plan above: no per-shot transport.** The development request already carries each shot's
own COLOR saturation: **request+1076 holds 12 signed saturation bytes**, packed by the stock packer `0x604c3051`
from the job parameters, which come from the capture record (+18600) or the compact slot (+382) [pub: fishcu's
native probes `penf_capture_conversion_probe.py` / `penf_processing_job_probe.py`]. Sectors 1–4 identify the film
exactly as the r8 recognition does from the settings. So the development hook recognises the film from the
request it is developing:
- live view, the saved JPEG, a RAW+JPEG second development and in-camera RAW edit each use the film of their own
  shot;
- no job-size change, no edits inside fishcu's H/L transport, no settings reads in the pipeline;
- cost: a film whose saturation sectors 1–4 were edited is no longer recognised (its name, WB and Blacks drop
  together, as they already do for the name and WB).

**Hook** (one 7-byte site): the stage list's tone-LUT builder call `0x604f85e8` (`mov d3,a0; call 0x604f7c76,…,28`)
becomes `call tn_tone,[d2,d3,a2,a3],28`. For a COLOR request (key word R+8 == `0x000b0000`, the test at
`0x604f74d8`) without an art curve (R+960 == 0), `tn_tone`:
1. sets C+56 bit 1 around the stock builder, so the curve is re-selected every pass (the stale-LUT trap), and
   restores C+56 for the later stages;
2. matches R+1076 sectors 1–4 against the film table;
3. for a film with Blacks / Whites, copies the LUT into the context's own buffer O+0x1234 if it isn't there, points
   O+0x1230 at it and remaps it with caduceus `remapBW()` (parameters lo / cB / cW / K precomputed per film, 8 B).

Only Blacks is used by the owner's 19 films: +1 for Gold 200, Ektar 100, Superia 400, Fuji C200, Agfa Ultra 100;
−1 for Kodachrome 64, Portra 800, CineStill 800T, CineStill 400D; −2 for Velvia 50. Whites is 0 everywhere but
supported.

**Size:** `tn_tone` 300 B of code + 152 B of film records, in the `osd` region after r8's block; 3,709 B of the region
left.

**Emulator** [emu], running the image's own patched site and the **real stock builder**:
- the stock image's COLOR pass gives the ROM tone curve `0x605fdd38`; COLOR with no film gives the same pointer,
  the builder sees C+56 | 2, and C+56 is restored;
- all 10 films with Blacks get a bit-exact `remapBW` of the ROM curve in O+0x1234; the 9 others keep the stock
  pointer;
- a curve the builder composed into the buffer itself (contrast path) is remapped in place; a stale buffer from a
  previous pass is rebuilt and remapped once (no double remap);
- only sectors 1–4 decide; a changed sector 1 drops the film;
- MONO, Cross Process and an art curve are identical to the stock image; d2/d3/a2/a3 and sp are kept;
- startup gate clean PASS; the `osd` region is reached only through the stub and our redirects.

**Not covered by the emulator:** the image processor's use of the LUT, live-view cost (one 256-entry remap per
pass, about 256 × 30 instructions), and the real scheduling of compact jobs on CPU2. The camera test plan
measures the shadow levels from photos; the effect is small, as on caduceus (Blacks ±1 moves the black end by
about 1–2 of 255 levels).

### v1.1: Blacks / Whites + split toning, built 2026-11-19 (not written)

The owner chose one camera round for both (2026-11-19). v1.1 = v1.1a plus v1.1b.

**v1.1b split toning** (`penf_films_v12.s`, private build `penf_films_v12_build.py`, checks `penf_films_v12_checks.py`):
- **Colours and maths:** caduceus-om3 `st_k` (12 wheel colours × R/G/B per step, `webapp/src/split.ts`) and `bend28`
  with Tone Balance 0, on 12-bit values from the 10-bit table: t = v<<2 | v>>8; ws = ((t·s>>12)·s)>>12,
  wh = ((t·t>>12)·s)>>12, s = 4095 − t; t' = clamp(t + ((Ks·ws + Kh·wh) >> 9)); kept rising; v' = t'>>2. Per film:
  6 × s16 K = st_k × camera steps (2 × the v0.26 strength), 228 B for 19 films.
- **Join hook** `0x604f62dc` (6 B → `jmp st_join` + nop): for a COLOR request with no art curve, sets C+100 |= 3 so
  this pass's tables are uploaded, recognises the film from R+1076 sectors 1–4 (as v1.1a), and bends each active
  bank (O+1052 / O+1056) in place. Then it replays the three replaced instructions.
- **Gate hook** `0x604f6139` (7 B → `jmp st_gate` + 2 nops): the stage's cache-hit skip would keep a table bent for
  the previous film, because the curve pointers don't change when the film does. Single-curve requests (R = G = B
  pointers, the only kind that gets bent) always take the copy path; per-channel curves (Cross Process, art) keep
  the stock skip.
- **Size:** the `osd` block is 2,872 B; 3,101 B of the region left.

**Emulator** [emu]:
- **The whole RGB stage**, run from the stage list's own call (`0x604f8586`) with the real selector and copier, base vs
  v1.1 on the same request. For the 10 films with a split tone, the table is a bit-exact `bend28` of the real copier
  output, still rising, with black and white unchanged. The other 9 films, COLOR without a film and a film with
  sector 1 changed give the stock table, with C+100 |= 3. MONO and Cross Process are identical to stock in full.
- **The join alone:** both banks bent; d2 = 0 → `0x604f631b`, d2 ≠ 0 → `0x604f62e2` with d0 = (64,sp); d2/d3/a2/a3
  and sp kept.
- **The gate alone:** stock copy, stock skip for per-channel curves, forced copy with (32,sp) = 1 for single curves.
- Deep-shadow tint: Gold 200 R−B +43/1023 at input 20; Portra 800 −29; Superia 400 green (R = B).

**Not covered by the emulator:** the image processor's use of the table, the live-view cost (256 × 3 entries ×
~35 instructions per COLOR pass with a split film, plus one table upload per COLOR pass), and whether stock
already sets C+100 for these passes.

### Phase 3: Films from the card

- **Start:** two tasks:
  - find the "card ready" gate, and check that the half-press method (or a boot-time task, as caduceus-om3
    v0.26.2 does) runs where file calls are allowed;
  - define `PENFMOD/LOOKS.BIN` with magic, length, CRC, a version and up to 15 films.
- **Build:** read `LOOKS.BIN` into the heap, check it, and fill the film list from it.
- **Tools:** the PEN-F Look Lab page exports `LOOKS.BIN` and can save it to the card
  (planned separately). A Python writer gives byte-identical files, for tests and
  for use without the page.
- **Done when:** films added on a computer show up on the camera after one half-press or at power-on, and a
  missing or broken file leaves the camera behaving as phase 2.

### Phase 4: Films on every COLOR, changes kept, names

- Films on COLOR 1 and 2 as well (five per COLOR, as caduceus-om3 does), so COLOR 3 is no longer sacrificed.
- **Changes kept:** `EDITS.BIN` written `.NEW` → read back → `.BAK` → `.BIN`. This needs card-ready writes and
  a state word, either from phase 1's writability test or from the heap.
- `*` for a changed film, and hold OK for "as built".
- The film name on the shooting screen, if a text route exists there.
- **Done when:** edits on a film survive a switch away and a power cycle.

### Phase 5: Look extras

The per-film WB shift moved into phase 2 (3.2b); split toning and Blacks / Whites moved to phase 2.1 (v1.1).
What remains here:
1. **Per-film Noise Filter, lens vignette correction off and Sharp:** one shared getter override, plus a true
   Sharp Off in `0x604f3ba1`.

Each is its own build and camera test.

**One rule for all of them:** values must travel with each capture and development job, as fishcu's H/L
transport does, because the PEN-F develops in several places (preview `0x6052010f`, recording `0x60531fdb`,
RAW edit, live view). A single global flag is the kind of shortcut behind caduceus-om3's RAW+JPEG grain
freeze [pub-cam].

### Phase 6: Grain and glow (research first)

- **Colour grain:** compare two routes in the emulator, then probe one on the camera:
  - the COLOR key plus four overrides (work list `0x604c58a0`, mask tone `0x604f75e5`, combiner selector
    `0x604fb7b8`, gain `0x604ea2ba`), which costs about 96 MiB of extra buffers per shot;
  - Grainy Film's texture pass without its grey pass.
- **Glow / Clarity:** find the Soft Focus strength site.
- **Done when:** grain on a colour photo stays in colour, with no extra delay and no freeze with RAW+JPEG.
  If neither route works, it stays out.

### Phase 7: Mono film presets

The same list mechanism after MONO 1–3, with presets made of stock MONO settings (filter, toning, grain,
contrast), as caduceus-ep7 does on the E-P7 [pub]. It reuses phases 2–4.

### Phase 8: Finish

- **Options**, chosen by the owner:
  - films on the dial positions as well as in the list;
  - a quick film-switch button;
  - the film name in EXIF.
- **Publish:** source and patch definition only, as for our other PEN-F patches: no firmware, decoded images or
  packages. Credit caduceus-om3 and caduceus-ep7 (Apache-2.0, keep their NOTICE where their data is used).

**Finish line:** films from the card in the Picture Mode list after Color Profile 1–3 (and MONO 1–3), edits
kept per film, and the look extras from phase 5, all [cam] on the owner's PEN-F, coexisting with HSL, Live ND
and the AF Limiter.

## 6. Risks

- **COLOR 3 is overwritten in the first version.** Phase 4 removes this.
- **Unproven space.** Sections 6 and 8 tails and the section-5 extension have never run our code. Phase 1
  exists for this.
- **Several development paths.** Look values must ride with each job (phase 5 rule).
- **Section load order.** All eight sections load before the camera runs, but caduceus-om3 bootlooped once
  calling late-section code from early pipeline code [pub-cam]. Code reached from the image pipeline should
  live in sections 1–5 or the section-5 extension.
- **HSL coexistence.** Every new site must be checked against fishcu's HSL release ranges, as our current
  builds already are.
- **Emulator limits.** Our emulator runs CPU code, not the image processor or the GUI's drawing. Anything that
  changes pixels or screens needs a camera test.
- **Recovery.** The SD updater has reflashed our builds many times [cam]. Recovery from a camera that will not
  start has never been tested on the PEN-F.

## 7. Sources

- caduceus-om3 v0.24.1 (local copy, tag `v0.24.1`, commit `015947a`) and v0.26.2 `ROADMAP.md`, `CHANGELOG.md`,
  `docs/PARITY.md` (GitHub API, read-only, 2026-11-11) [pub].
- `OM3_PORT_PLAN.md` on branch `om3-port`, commit `ece7bf6`: caduceus-om3's hooks and code-space use.
- This repository: `docs/color/pen-f/*.md` (fishcu) and `patches/hsl/pen-f/`.
- The owner's private PEN-F project notes: creative dial map, AF limiter map, Live ND map, build record.
- [research/penf_caduceus/](research/penf_caduceus/README.md): the four research notes behind this plan.

## Upstream watch: caduceus-om3 v0.27 / v0.27.1 (read 2026-11-11 through the GitHub API) [pub]

- **v0.27.1:** fixes a rare freeze at switch-on. v0.26.2's automatic film load read the card and refreshed
  settings while the camera was still building its start screen; live view started, nothing else did, and the power
  switch was dead until a battery pull. Films now load at the first half-press again. This is the same lesson as
  our films v1 boot loop and the v1-r2 freeze: no settings work during startup, and nothing that blocks across
  tasks.
- **Film name and recipe in every JPEG** (v0.27): Image Description `FILM n Name`, and a User Comment with a
  versioned recipe code (`docs/PHOTO_CODE.md`, devkit). This is our phase-8 "film recipe in EXIF" item. Adopting
  their code format would make PEN-F photos readable by their Control Panel and tools.
- **Creative Dial modes:** each dial position (CRT / ART / COLOR / MONO) can be set to a mode and remembers its
  own COLOR k or film. The PEN-F has the same dial; this is a model for a later version of our parked ART/CRT idea
  (3.3).
- **All four arrow keys in Button Function.**
- **Optional on-card debug log** (`DEBUG.TXT` → `CADLOG.TXT` at each shutter event). Worth copying: it would let
  us read the camera's state after a test instead of inferring it.
- **256 KiB more section-6 space,** proven on the OM-3 with a loader change. It doesn't transfer: the PEN-F's SD
  updater lives in section 5 and runs after that loader step (phase 1, shelved).

## Upstream watch: caduceus-om3 v0.28 → v0.40-beta3, caduceus-ep7 → v0.34a (read 2026-11-19) [pub]

Read only, from both repositories' CHANGELOG / release notes; caduceus-ep7 is `cakelesscoder/caduceus-ep7`. Nothing was
uploaded. The split table was saved to the private project as `probes/data/caduceus_split_v0.30.json` (Apache-2.0, credit
kept).

| Upstream feature | Where | PEN-F route | Priority |
| --- | --- | --- | --- |
| Split toning 0–10 in half steps + Tone Balance | om3 v0.28 (`bend28`, st_k table) | v1.1b: the copier-join bend at `0x604f62dc` (section 2 of 06_TONE_SPLIT), film recognised from request+1076 as in v1.1a; 10-bit table, `>>9`, balance 0 | **next** |
| Blacks / Whites to ±7 | om3 v0.28 | v1.1a already has it (the films use ±2 at most) | built |
| RGB curves (5 points per channel) | om3 v0.30 (`st_run` adds the curve deltas in the same pass as split) | same stub as split, ≈ +100 B; per film 15 B | v1.2 |
| Colour mix: 3×3 matrix in the image hardware, no time cost | ep7 v0.34 | find the PEN-F colour-matrix stage (research); the best value per byte if it exists | research |
| Colour-matched / regraded films (`CURVES.BIN`) | om3 v0.29 / v0.30 | data only: rebuild the 19 films from their current set once split + curves exist | with v1.2 |
| Halation | om3 v0.28 → v0.30.3 / v0.40-b3; ep7 v0.31 → v0.34a | a CPU pass after development; ep7's watchdog restarts (v0.31a/b) and om3's Rec View fix (v0.30.2) are the traps | later |
| Own colour grain, strength 1–5 + size | om3 v0.40-alpha | CPU pass, same traps as halation | later |
| Film name + recipe in EXIF | om3 v0.27/v0.28, ep7 v0.31d | we already write tag 0x101c (H6); add ImageDescription / UserComment in their format | small |
| XPan / 21:9 / 5:4 crops, frame lines | om3 v0.40-alpha/beta, ep7 v0.29/v0.32 | large GUI + JPEG-size work | later |
| Debug log `CADLOG.TXT`, crash record `CRASH.BIN` | om3 v0.27+, ep7 v0.33 | worth copying for our camera tests | later |
| Per-row shooting-screen info ticks | om3 v0.40-beta/b2 | the PEN-F has its own LV-Info checklists (HIDDEN_ITEMS_MAP) | skip |
| Custom modes keep their own films | om3 v0.29.2–v0.29.5 | only matters once films are stored per COLOR | later |
| Video / 4K bitrate / AP colour | ep7 | owner doesn't use video | skip |

**Lessons to check against our builds:**
- **om3 v0.30.4-alpha:** stepping through films quickly rebooted the camera because each step wrote the settings
  memory; now it writes once on leaving the list. Check what our film pick writes per step in the strip (r8's set path).
- **om3 v0.30.2 / ep7 v0.31:** pixel effects must skip a shot's small extra pictures (review image), or the review goes
  black and live view can freeze. This applies to halation and grain, not to the curve and table bends in v1.1.
- **ep7 v0.31a/b:** long CPU passes trip the watchdog; yielding mid-photo crashed on bright frames. Keep effects short.
- **ep7 v0.34:** code that runs early in boot must not call later sections (the same as our lesson 4).

**The owner's 19 films with a split tone** (v0.26.2 data, v0.26 units): Gold 200, Kodachrome 64, Portra 800,
CineStill 800T, Pro 400H, Superia 400 (shadows Green 2), CineStill 400D, Fuji C200, Vision3 250D, Fuji Eterna. Most
of them are strength 1 = camera step 2 of 10, so the effect is subtle.
