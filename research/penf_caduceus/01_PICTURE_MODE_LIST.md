# PEN-F: films in the Picture Mode list after COLOR 1–3 (build 3101)

Research pass, 2026-11-11. Read-only. Labels: **[static]** code/data reading of the
decoded main (base `0x60021020`), **[emu]** run natively in the repo's MN103 engine
(probes in `agentA/tools/`), **[pub]** read from caduceus-om3 docs (OM-3, not checked
on the PEN-F). Nothing here was tried on a camera. Claims taken from repo docs
(CREATIVE_DIAL_MAP.md, EDITOR.md, SETTINGS_STORAGE.md, CODE_SPACE.md, BUILD_RECORD.md)
are marked [static] with the doc named.

## Verdict

**Feasible in a small form, with the same trick caduceus uses.** The PEN-F's picture
mode list is built the same way as the OM-3's: a per-family table of value records,
one builder function, a generic list model, and value-keyed label/icon arrays
[static, emu]. A film value that only the list builder, the list's labels and the
setter see, and that becomes "COLOR k" everywhere else, needs **no public modes 63+**,
no rule-map changes and no profile-loader cases [static].

The full caduceus v0.24–v0.26 feature (20 films, per-film edit memory in a card file,
drawn FILM pictures, '*' tracking, reset tables) is **not feasible yet**. It needs
tens of KB of code (caduceus: about 61 KB in a proven 64 KiB extension) [pub]. The
PEN-F currently has about 1.2 KB of proven free space left in loaded section tails
[static, BUILD_RECORD.md / CODE_SPACE.md], and no card-file code. A PEN-F
section-end extension probe (like caduceus GX1/GX2) would have to come first.

**Minimum viable version:** N built-in films (about 4–6) listed after COLOR 3, each
loaded onto **COLOR 3**. Labels are text; the icons are COLOR 3's. There is no per-film
edit memory. About 250–300 B of code and 200–400 B of data.

**Cheaper alternative (coordinator's (b)):** films on the ART and CRT dial positions.
About 150 B in total, with no GUI-list work. It gives 2 films and loses ART/CRT on the
dial. See section 8.

## 1. Where the list's entries come from

### The cell's setting is 906, and the list is COLOR's own setting 910

- The Super Control Panel (SCP) / Live Control "Picture Mode" cell uses setting
  **906** [static]. 906 is a type-5 setting whose value is a family id, list
  `{907,908,909,910,976}` (descriptor `0x603e3f14`). It is item **idx 26 (0x1a)** in
  the screen maps (for example the pair `{906, 26}` at `0x60f651a0`).
- Per-setting list builders: table `0x60f489c0`, 8-byte `{setting, builder}` records,
  searched at `0x60c7f0fb`. **906 → `0x60c7f779`**, 908 → `0x60c7fb93`,
  2338 → `0x60c8114d` (always 911) [static].
- **Builder `0x60c7f779`** [static, emu]:
  - reads `GetValue(906)` and `GetValue(26)`. When 26 ∈ 3..6 (PASM) it picks the
    family setting and its record table:

    | 906 | list setting (this+84) | records | count (immediate) |
    | --- | --- | --- | --- |
    | 907 | 907 | `0x60f49024` | 8 |
    | 908 ART | 908 | `0x60f49084` (`0x60c7f7c8`) | 30 |
    | 909 CRT | 909 | `0x60f491ec` | 1 |
    | **910 COLOR** | **910** | **`0x60f491f8`** (imm32 at `0x60c7f7f4`) | **3** (`mov 3,a3`, bytes `9f 03` at `0x60c7f7fa`) |
    | 976 MONO | 976 | `0x60f4921c` | 3 (`0x60c7f80f`) |
    | otherwise | 911 | `0x60f48eec` | 26 |
  - **COLOR records** (12 B `{u32 API value, u32 availability id, u32 func}`):
    `{54, 1048, 0x60c7eac4}`, `{55, 1049, 0}`, `{56, 1050, 0}`. MONO:
    `{57,1051,f}`, `{58,1052}`, `{59,1053}` [static]. The table at `0x60f491f8` is
    referenced only by the builder (`0x60c7f7f2`) [static].
  - **Native run** (`tools/builder_probe.py`, facade modeled) [emu]: for each record it
    checks availability (func(value), or `GetValue(id)` when func = 0), then
    `selectable(910, value)`. It stores `values[i] = record.value` at this+100 and
    disabled flags at this+96, and sets the count at this+88 and the cursor at this+90
    (where `values[i] == GetValue(910)`). Result `values=[54,55,56]`, cursor 1 for
    COLOR2. With 1050 = 0 the list is `[54,55]`. This is the OM-3 design one-to-one
    (OM-3: setting 901, builder `0x611b3250`, 20-B records) [pub].
- **List model** [static]: vtable `0x60f49c00` (slot 1 cursor +90, 2 count +88,
  3 disabled(i) +96, 4 value(i) +100). The constructor `0x60c7f05d(id, &want)` runs the
  builder through `0x60c7f0b2`. It is the same model class the menu picker
  `0x60d0418d` reads (LIVE_ND_MAP).
- **Commit** [static]: the model's commit handler (example `0x60c82155`, events
  0x900c / 38699) calls facade **setSetting(this+84, 0, values[cursor])**, so
  `setSetting(910, 0, 55)`.
- **What 910 is** [static]: a type-6 compound setting (descriptor `0x603e0800`) with
  4 records of 64 B: `{2,0}`, `{11,1}`, `{11,2}`, `{11,3}`, and the API table at
  `0x603cd850`: **{1, 54, 55, 56}**. The members are 910's raw value (11 = COLOR) and
  **1086** (profile). Rules on 111 (`0x6039cb34`, rules 42–44): `1083=910, 910=11,
  1086=k → 54+k−1`. 910's own rule set (`0x603a173c`) maps in API space
  (`{1,54,55,56} → 1` when 601/1245 force Natural). So `setSetting(910, 0, 55)` sets
  1086 = 2, and public mode 55 follows.
- **Menu**: the Shooting-menu Picture Mode row looks like virtual setting 2338
  (builder `0x60c8114d`, always 911's 26 records, where COLOR is the single value 54).
  So films would show only in the SCP / Live Control list with the dial at COLOR in
  PASM [static, inference]. MONO uses the same design with 976 / 1087.

### Counterparts of caduceus' pieces

| caduceus (OM-3) [pub] | PEN-F | evidence |
| --- | --- | --- |
| setting 901 value records (`fl_rec`) | 910 records `0x60f491f8` (3×12 B) + count `0x60c7f7fb` | static, emu |
| list builder 0x611b32ae (cursor GetValue) | `0x60c7f779`; cursor `GetValue(910)` returns to **`0x60c7f898`** | emu |
| facade selectable (sl_sel) | facade slot 9 `0x6073567b` → `0x6075f6ad` → rules `0x602b9ef3(id,v,2,2000)`; called from `0x60c7fa30` (ret `0x60c7fa32`) | static, emu |
| facade SetValue (sl_set) | facade slot 0 `0x607363b3(id, mode, a1=value)` (vtable `0x609a4660`) | static |
| facade GetValue | facade slot 2 `0x607359ef` → `0x6075f551` → `0x602bad44` (API value through descriptor+8 table) | static |
| availability `GetValue(1072..1075)` | `GetValue(1048..1050)` / func `0x60c7eac4` | emu |
| item 111's 3 lists (title, left cell, strip) | CmnAllSetting item table `0x60f5bc30` (52-B records, 54 + 1 entries, set table `0x60f5c75c`, lookup `0x60c91f05`). **idx 0x1a** record `0x60f5c1ac`: +4 icons `0x60f58fc0` (72, 50×38), +8 icons `0x60f59680` (72, 64×48), +28 Partial Color sub-list `0x60f599e0` (6), +36 labels `0x60f59a28` (72) | static, emu |
| left cell 0x611d08f4 | not identified; the SCP grid cell / Live Control readout calling `GetValue(910)`. Find it with an emulator trace of facade return addresses | open |
| "COLOR changed?" 0x6129ba07, '*' pictures | none found: the 72-entry icon arrays have no starred variants | static (negative) |
| quick-menu pictures 15746.., live-view 15706.. | value→bitmap tables keyed by 54..59: `0x60fd7ff4`, `0x60fd7e8c`, `0x60f71b84`, `0x60ef7044`, `0x60f62cd0`, `0x60f63030` (consumers not identified) | static |

## 2. Facade (OlyApiSettingController)

The singleton is at `0x61602868` (getter `0x607355e9`), vtable `0x609a4660` in ROM
[static]. Slot 0 `0x607363b3` setSetting(d0 id, d1 mode, a1 value); slot 2 `0x607359ef`
getSetting(d0, a1 = &out); slot 6 `0x60735a11`; slot 7 `0x60735c39` value-by-index
(`0x6075f62e`); slot 9 `0x6073567b` selectable; slot 26 `0x6073588b` API shooting mode
(`0x602ba340`). The builder reaches all of them with `calls (a2)`, so the return
address is in MDR [static, emu].

**Wrapping options:** (a) redirect vtable words in ROM (data-only:
`0x609a4660` slot 0, `0x609a4668` slot 2, `0x609a4684` slot 9) to small wrappers that
test `id == 910` (and MDR for the getter), then tail-jump to the stock functions.
(b) Hook only the builder sites. (a) also catches the commit handler(s), wherever
they are.

## 3. Titles and icons

- Strings (component 1, row 8; `tools/strs.py`) [static]: 2749–2751 "Color Profile
  1–3" (SCP labels), 2752–2754 "@A0B2@…" (menu, with icon glyph), 2757–2759
  "Monochrome Profile 1–3", 2859–2864 "Color/Mono Profile n", 203 "Picture Mode".
- Bitmaps (OSD bank, 4665 entries, table `0xa26abfac` in component 1) [static]: COLOR
  1–3 = 4350–4352 (50×38) and 4344–4346 (64×48); MONO 4353–4355 / 4347–4349.
- Lookup **`0x60c8972a`** (value, options, count, out) is the generic value→label
  routine; it has about 250 callers, including the SCP popups `0x60c8f…`–`0x60c91…`
  and `0x60cfbb..` [static].
  `tools/label_probe.py` [emu]:
  - labels 54/55/56 give type 4, strings 2749/2750/2751;
  - icon arrays give type 3, bitmaps 4350–4352 and 4344–4346;
  - **a value not in the array writes nothing** (stale label, the LIVE_ND lesson);
  - a one-record type-5 array gives UTF-16 "FILM 1" in out+8.
- **New bitmaps are not practical** (the table lives in OSD component RAM). Films
  reuse COLOR 3's icon, or an ART icon, and show their name as type-5 text.

## 4. Can a value past COLOR3 flow through rules and loader? (the trick)

- With caduceus' trick, the settings engine never sees the film value: the setter
  wrapper turns `setSetting(910, 0, FV+j)` into "load film j onto COLOR k", then
  `setSetting(910, 0, 54+k−1)`. Everything downstream then sees 910 API 54+k−1 →
  1086 = k → public 111 = 54+k−1 → profile loader `0x602c414a` case 54+k−1 [static].
  **No new public modes, no changes to the 57-entry maps, and the jump table
  `0x603a3be4` stays as it is.**
- If FV reached the engine, it would be unknown: not in 910's API table
  (`0x603cd850`), and passed unchanged by 910's rule maps. `selectable(910, FV)` is
  likely refused (open; emulator check of `0x602b9ef3`). So a selectable wrapper is
  advisable (~16 B).
- The SCP cell **dial stepping** (turning a dial on the highlighted cell) probably goes
  through the settings stepper over 910's descriptor list (`0x602bab99`), not the list
  model, so it would skip the films. caduceus needed a separate change for this in
  v0.26.2 [pub]. Open [static, inference].

## 5. What a film writes into COLOR k

- Stored ids per COLOR k [static, picmode_scout + loader case listing at
  `0x602c4bbf`]:
  - COLOR1: 916, 913, 967–969, 1111, 931–942
  - COLOR2: 917, 914, 970–972, 1112, 943–954
  - COLOR3: 918, 915, 973–975, 1113, 955–966

  That is 18 each, read with bank getter `0x602bc3ca(ctx, part, id)`. Plus the HSL
  extension's part-1 words of 931–966 (12 per COLOR, format `0x4831CCVV`)
  [static, SETTINGS_STORAGE.md].
- Per-COLOR UI state: 912 (editor selector), 1095/1100/1101 cursors [static,
  EDITOR.md].
- **Two storage strategies:**
  - **S1, write-through** (as caduceus `fl_sw`/`pf_put` [pub]): write the film's 18
    values (+12 HSL words through `0x602f0710`) into COLOR k's stored ids. Then the
    editor shows and edits the film. COLOR k's own settings are lost unless backed up,
    and there is no spare bank storage for a backup. So COLOR 3 becomes "the film slot".
    Writes from the GUI task should use facade slot 0 (it posts to the app task;
    EDITOR.md chain `607363b3 → 6075fbed → 602b9dac → 602badc5 → 602c50be`). That is
    18 refreshes per load: timing needs the emulator, then the camera.
  - **S2, read-redirect:** hook `0x602bc3ca` (or the loader's case-56 block
    `0x602c4bbf..0x602c4ce6`): when MDR is in that block and a film is active, return
    the film's value. No writes, and COLOR 3 is kept. But the COLOR editor would edit
    COLOR 3's stored values with no visible effect. HSL H/L comes from the HSL
    extension's own reader, which needs its own hook.
- **Persistence of "film j on COLOR k":** RAM-only unless a spare stored byte is used.
  Candidates: settings **399** (Picture Send Size) and **400** (Picture Copy Size),
  PENPAL rows on a body with no accessory port. Each has its own 1-byte store key
  (`0x6221` / `0x6271`, table `0x603fa158`), and no rule set targets them. 399 has
  about 22 code sites still to check [static, partial].
- **Reset / changed paths** [static]: editor held-OK (timer 537 → `f802` → `903e`)
  resets the wheel children to COLOR k's stock defaults, not the film as built
  (EDITOR.md). Shooting-menu Reset resets the COLOR ids through the defaults table
  `0x603c8bb0`. No '*' markers were found to maintain. With S1 the reset gives the
  stock COLOR 3. With S2 it changes COLOR 3's hidden values.

## 6. Edit list: minimum viable version (films on COLOR 3, S1, no edit memory)

| # | Where | Change | Size |
| --- | --- | --- | --- |
| 1 | new data | record table `{54,1048,0x60c7eac4},{55,1049,0},{56,1050,0},{FV+j,1050,0}×N` (FV for example 0x7F00; check that no option array uses it) | (3+N)×12 B |
| 2 | `0x60c7f7f4` (imm32) | → new table | 4 B in place |
| 3 | `0x60c7f7fb` (imm8) | 3 → 3+N | 1 B in place |
| 4 | vtable `0x609a4684` (slot 9) | → `fl_sel`: 910 and value ≥ FV → 1, else stock `0x6073567b` | ~16 B |
| 5 | vtable `0x609a4660` (slot 0) | → `fl_set`: 910 and a1 ≥ FV → `fl_load(j)` then stock(910, 0, 56); else stock | ~40 B |
| 6 | new code `fl_load` | loop over an 18-id table, setSetting(id, 0, film[j][i]); optional 12 HSL words through `0x602f0710` | ~70 B |
| 7 | `0x60c8972a` entry (5 B: `mov a0,(4,sp); clr d2; clr d3; cmp d2,d1`) | jmp `fl_lk`: d0 ≥ FV → if a1 is a label array, use a synthetic type-5 record {FV+j, 5, 0, name}; if an icon array, use value 56; else stock. Re-run the 5 bytes, jmp `0x60c8972f` | ~90 B |
| 8 | data | N × 18 B film values (+ N×48 B HSL), N names (~8 B) | ~110–400 B |
| 9 | optional: vtable `0x609a4668` (slot 2) | `fl_get`: id 910, MDR = `0x60c7f898` (builder cursor) and film active → FV+j | ~30 B |
| 10 | optional | persist the film index in setting 399 (descriptor list, rules check) | ~10 B + data |

Totals: about 250–300 B code and 200–400 B data. Placement: the section-3 tail
(`0x6069b26c..0x6069b800`, with H4/H5 at `0x6069b270..`, `align_tramp` at `0x6069b299`,
array B at `0x6069b7bc`; about 1.2 KB left) [static, BUILD_RECORD.md]. Recheck the
current build's occupancy before placing anything.

Not included: films in the menu (2338 → 911 list), SCP dial stepping, film name/icon on
the SCP grid cell and the shooting screen (they show COLOR 3), and per-film edit memory.

## 7. Risks and tests

- **Emulator first:**
  1. trace every facade `getSetting(910)` return address while the SCP, Live Control
     and popup open (find the left-cell equivalents);
  2. `selectable(910, FV)` through the real rules engine;
  3. builder plus lookup hook with N films (count, cursor, disabled flags, labels,
     icons);
  4. `fl_load` → the 18 setters → one profile refresh → effective settings;
  5. that the commit handler for the 906 model really goes through vtable slot 0;
  6. HSL-build coexistence: the HSL code and the section-3 tail.
- **Camera:** the list shows the films; selecting one applies it (photos); power cycle
  (S1 values persist; the list highlights COLOR 3 unless #10); C1–C4 recall; menu
  Reset; editor held-OK reset; no crash when capturing right after a switch
  (caduceus' v0.24 reboot came from a settings getter during capture [pub], so keep all
  film work out of the capture path).
- **Specific risks:**
  - a stale label for any other consumer that sees FV (mitigated by the trick);
  - 18 GUI setter round-trips per load (latency; lock-ups if called from the wrong
    task);
  - the vtable redirect affects every facade client (keep the fast path a few
    instructions);
  - the overwritten COLOR 3 (S1).

## 8. Alternative (b): films on the ART / CRT dial positions (as caduceus v0.27 [pub])

- Dial to 906 writer `initPictureModeDialSetting` `0x60ba4df4`: ART `0x60ba4e58`
  (`mov 908,d1` at `0x60ba4e5b`), CRT `0x60ba4e70` (`mov 909,d1` at `0x60ba4e73`), common
  write `call 0x60b9c927` at `0x60ba4e99`. Dial translation table `0x609554dc`
  `{1,1}{2,2}{3,3}{4,4}{5,5}{0,0}` [static, CREATIVE_DIAL_MAP.md §6].
- **Prefer the 906-constant route to the table remap.** Remapping the table makes
  COLOR↔ART look like no change to the change detector `0x60b9b1da` (old = new = 4),
  so nothing would refresh [static, inference]. Instead: 908→910 and 909→910 in those
  two constants (2 small edits), plus a stub on the `0x60ba4e99` call. The stub sets
  "film A" (ART) / "film B" (CRT) / none (COLOR) by dial state, sets 910 API 56 for a
  film, and restores the previous profile on COLOR.
- **Use S2 read-redirect** (hook `0x602bc3ca` for the case-56 block). The dial position
  is then the persistent state, COLOR 3 stays intact, and there is nothing to back up.
  The creative editor opener `0x60c63ac2` already skips ART (state 2). It opens for CRT
  (state 1), so make it skip state 1 too (1 compare) and editing a hidden COLOR 3 is
  not reachable from a film position.
- **Size:** about 120–150 B code + 2×18 B data; no list, label or vtable work.
- **Cost:** only 2 films, and ART/CRT leave the dial (ART still reachable where 911
  applies). The ART-state GUI code `0x60c14846` and the shooting-screen icon need an
  emulator / camera check, because state 2 still reaches some readers.
- **Effort compared with (a):** roughly one third of the code, with no GUI-list
  surgery. The same loader (S1) or redirect (S2) core can later serve (a).

## 9. Open questions

1. The left-cell / SCP-grid / Live Control readout sites (facade return addresses), and
   which value→bitmap table each display uses.
2. `selectable(910, FV)` with stock rules; and is the obj2 gate (`0x606f9214` vt0) on
   for 910?
3. The commit handler class for the 906 model (`(76,this)` = `0x60c844e5` after the
   builder) and its exact setSetting call.
4. SCP dial stepping path for 906/910.
5. Whether 399/400 are truly unused (all sites, C1–C4 bank cells, Wi-Fi resize).
6. Whether the HSL release touches `0x602bc3ca`, the loader or the section-3 tail ranges
   used here.
7. A PEN-F section loader-end extension (needed for anything near the caduceus
   feature set).

Probes: `agentA/tools/builder_probe.py`, `label_probe.py`, `strs.py`, `recs.py`,
`desc.py`, `words.py`, `refs.py`, `find_sid.py`.
