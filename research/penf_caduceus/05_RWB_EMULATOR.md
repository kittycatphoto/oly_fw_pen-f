# R-WB: per-film WB shift, emulator pass (2026-11-11)

Research item R-WB from roadmap 3.2b (option a, accepted as the v1 plan). Emulator and code reading only:
nothing was built for the camera or written to a card. The prototype is in the private project's
`probes/wb_film.s` and `probes/wb_research.py`. It runs on the PX1 payload with the stub placed at
`EXT+0x400` in an emulator-only image.

## 1. The sites [static]

All reads of the WB fine-tune keys were found by searching the decoded main for an immediate load of each key.
There are **16 loads (8 A-B / G-M pairs)**, not the "about 9" estimated earlier. Every one is followed, 2–8 bytes
later, by the same 7-byte call `call 0x600750ee,[d2,d3],12`. Its arguments are d0 = key, d1 = preset index,
a0 = 0, and it returns the value in d0.

| Pair (A-B load / call, G-M load / call) | Index | Stored to | Use |
| --- | --- | --- | --- |
| `0x6054f1dd`/`f1e6`, `0x6054f1f8`/`f200` | 0 | capture +18640 / +18642 (16-bit) | capture, WB mode 1 |
| `0x6054f33b`/`f343`, `0x6054f34e`/`f358` | 15 | (a0) / (a3) | capture, a preset case of the mode table |
| `0x6054f3cc`/`f3d5`, `0x6054f3e3`/`f3eb` | 0 | capture +18640 / +18642 | capture, WB mode 2 |
| `0x6054f4ba`/`f4c3`, `0x6054f4d4`/`f4db` | 0 | capture +18640 / +18642 | capture, WB mode 4 |
| `0x6054f525`/`f52f`, `0x6054f540`/`f548` | 1 | capture +18640 / +18642 | capture, the default case |
| `0x6055741c`/`7425`, `0x60557431`/`743a` | 0 | compact record +48 +88 / +90 (byte) | live view |
| `0x60567dcc`/`7dd4`, `0x60567de4`/`7dec` | (12,sp) | `0x61bcab09` / `0x61bcab0a` (byte) | not named; another live/state copy |
| `0x60af5513`/`551c`, `0x60af5527`/`5530` | d2 (≠ 0) | record +18640 / +18642 | in-camera RAW edit |

Each call is redirected by changing its 4-byte displacement in place, so the sites need no code space.

## 2. The stub [emu]

`wb_get` takes **95 bytes** and is entered exactly as the getter. It works in this order:
1. Runs the stock getter.
2. Reads setting 111 (effective picture mode). If it is not 56 (COLOR 3), it returns the stock value.
3. Reads the film-state setting. If it is not between 1 and N films, it returns the stock value.
4. Takes the film's byte (high nibble A-B, low nibble G-M, signed).
5. Sign-extends the stock value from 16 bits, adds the shift and clamps to −7..+7.

Callee-saved registers and the stack come back unchanged.

## 3. Emulator results [emu]

- **Stub alone:** **80 cases pass**:
  - both keys;
  - stock values 0, 2, −3, 6, −6;
  - COLOR 3 with no film, COLOR 2 with a film number set, films 1–5 (shifts 0, ±3 / ∓2, 7 / 1, −7 / −1), and an
    out-of-range film 6.

  The getter is modelled to return 16-bit values, as the capture code stores them.
- **Stock code at real sites:** the instructions from the key load to the stores were run with the 16 calls
  redirected, the key getter modelled with stock A-B +2 / G-M −1, and setting_get modelled. All three sites gave
  the same results:

  | Case | Capture, WB mode 2 (`0x6054f3cc..f3f8`) | Live view (`0x6055741c..7444`) | RAW edit (`0x60af5513..553b`) |
  | --- | --- | --- | --- |
  | COLOR 3, no film | 2 / −1 (stock) | 2 / −1 | 2 / −1 |
  | COLOR 3, film +3 / −2 | **5 / −3** | 5 / −3 | 5 / −3 |
  | COLOR 3, film +7 / +1 | **7 / 0** (clamped) | 7 / 0 | 7 / 0 |
  | COLOR 2, film number set | 2 / −1 (stock) | 2 / −1 | 2 / −1 |

  Live view stores a byte and capture a 16-bit word; both read back as signed values.

## 4. Still open

1. **Film-state setting.** Neither candidate is free [static]:
   - **399** is read by `setting_get` at `0x607ca17b` and tested for the values 3 / 5 / 7;
   - **400** is loaded before calls in about 70 places.

   **Update (v1 build, 2026-11-11): the film state is 597, not 598.** 598's descriptor is type 6 (a compound of
   four 64-byte records), so it can't hold a film number. 597 (hidden E-M1 [HDR]+[BKT] button option) is a type-1
   byte setting with store key `0xe8c1`. Its only readers (`0x60b9633b`, `0x60b96376`) test `== 1` [static], so
   the build stores film j + 2 (2..20) and widens its value list to the stock 0..29 list `0x603df6a7`,
   length 21. The rules engine allows 0..20 and forces nothing [emu]. The 598 reasoning below is kept for the
   record.

   ~~598 (hidden C-AF Lock) is the choice~~ [static]:
   - the hidden-items audit (2026-11-02, `HIDDEN_ITEMS_MAP.md` in the private project) found it dead: its
     `mov 598,a0` hits at `0x6055xxxx` are struct offsets and the rest are menu code, so nothing in AF or
     imaging acts on it;
   - it has its own store key (`0xe8d1`, index 0), so it is saved like other settings and survives power-off;
   - its value list is Off / Low / Normal / High (4 values), and film numbers need 0..19. Live ND showed the
     setting store doesn't clamp values (setting 267, [emu]); only menus and rule maps act on lists. So the
     film setter can write the number through the store, or 598's descriptor list can be widened, as was done
     for setting 448 (AF Limiter).

   **Phase-2 emulator check:** write 598 = 19 through the chosen setter, read it back, run the rules engine, and
   confirm nothing changes it.

   A menu Reset puts 598 back to its default. That turns the WB shift off while COLOR 3 still holds the film's
   other settings; the film list's own state has the same behaviour, so the list should show COLOR 3 then.
   Fallbacks:
   - a single-user CRT id (895–897 or 1110), which is lost if the owner uses CRT;
   - a RAM word, lost at power-off. That means no WB shift after a restart until a film is picked again, so a
     persistent setting is better.

   The film list needs the same state.
2. **Live-view effect.** Whether the compact byte pair actually drives the preview's WB, and what the
   `0x61bcab09` pair feeds. Not traced; the PX1-based film build shows it on the camera.
3. **Stock getter representation.** The stub sign-extends from 16 bits, which is correct whether the getter
   returns a 16-bit or a sign-extended value.
4. **Colour result.** The emulator doesn't model the image processor. The WB effect on photos needs a camera
   test.

## 5. Bytes for v1

- 95 B stub;
- 16 × 4-byte displacement edits in place;
- 1 B per film in the film table.

Total with the 19 films: about 1.45 KB, inside PX1's 4 KiB.

## 6. Camera result and trace (2026-11-12)

**Camera:** the film WB shift doesn't appear (r4 and r5):
- r5, WB Auto, A+4 G−3 set by the owner: `WhiteBalanceBracket` is `4 -3` on COLOR 2, Gold 200 and CineStill 800T alike.
- r4, Fine Weather: COLOR 2 (PB110007) and Gold 200 (PB110008) both have `WB_RBLevels` 478/476. A preset fixes these
  levels independent of the scene.
- The film's saturation is in the maker note (`ColorProfileSettings`), so the values `fl_ident` reads are in place [cam].

**Trace** [static]:
1. All 16 getter calls point to `wb_get` (`0x60a79ef4`) in the r5 image.
2. The WB mode switch in capture set-up (`0x6054f1ab`, mode at record +18558): modes 1/2/4/default read the fine-tune
   through the hooked calls. Mode 3 zeroes it (`0x6054f44c`). The values go to capture record +18640/+18642.
3. **A second read path exists.** `setting_get`'s id-to-key table `0x603fa158` (1,293 words, index<<16 | key)
   maps settings **39 / 132** (index 0), 144 / 145 (index 14) and 16 more pairs to the same store keys
   `0x84f9` / `0x9679`. `setting_get` (`0x602f037b`) caches a pointer to the stored value through `0x600750c4` and
   reads it directly, **bypassing `0x600750ee`**. Any reader of those setting ids sees the stock value.
4. No other code loads the keys as immediates. The other byte hits are data or coincidental.
5. The maker-note source of `WhiteBalanceBracket` is not pinned down. The record +18640 is also read by a generic
   capture-parameter accessor (`0x60307100..0x603072e8`, ids 512..2561 by hash), which may feed it.

**Ranked causes:**
1. **`fl_ident` returns −1 on the camera.** The r4 list cursor never landed on the film either, and it uses the
   same recognition. Two independent features act as if no film is recognised. Suspects: setting_get(111) isn't 56
   for COLOR 3 (the 111 = 54..56 mapping is from the rule tables, never read on the camera), or setting_get's
   returned saturation isn't the signed menu value the nibble packing assumes.
2. **The image WB doesn't come from the capture record**, but from settings 39 / 132 through `setting_get`, which
   bypasses the hook.

**Next:**
- A diagnostic build (r6): the label for COLOR 3 shows the film's name when `fl_ident` recognises it. Otherwise it
  shows the raw setting_get(111) value and the packed saturation bytes. The SCP cell then reads out the
  recognition on the camera, which separates cause 1 from 2.
- A fix for 2, if needed, moves the shift to the store read for the 0x84f9 / 0x9679 keys (`0x600750c4` pointer
  users), or to the capture-record writes.

## 7. Resolved (2026-11-12) [cam]

- **Cause:** the r6 diagnostic read `?0B 0400FF01`. setting_get(111) returns **11** (the COLOR family code) with
  COLOR 3 active, not the public mode 56, so `fl_ident` never recognised a film. Path 2 (settings 39 / 132
  bypassing the hook) didn't matter for capture.
- **r7 fix:** COLOR 3 = 111 == 11 with profile setting **1086 == 3** (or 111 == 56).
- **Camera result:** `WhiteBalanceBracket` 7 / 4 / 2 for Gold 200 / COLOR 2 / CineStill 800T, with the owner's A+4.
  The WB gains follow (R/B 496/620, 470/668, 454/692). Cursor and COLOR 3 title correct.
- **Note:** a film's shift adds to the owner's own fine-tune and clamps at ±7 (Gold 200 on top of A+4 gives 7).
