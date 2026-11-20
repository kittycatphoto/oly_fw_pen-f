# OM-3 1.1 → PEN-F 3.1 address map (caduceus-om3 hook sites and helpers)

Read-only static work. Both mains base 0x60021020.
- OM-3 main decoded from `OLY_E_147_1100_0000_0000.BIN` with `oly_container.py --code-base 0x60021020`:
  `om3_decoded/out/00_0100_50000020.decoded.bin`, sha256 `5e8d376e9111…8c5b7d59`. That matches caduceus's `5e8d376e…7d59`, prefix and suffix.
- PEN-F main: `analysis/penf_3.1/00_0100_403a0020.decoded.bin`.

## Method (scripts in `agentD/scripts/`)
- `tokenize.py`: one objdump linear sweep per image, saved as an instruction table (OM-3 12.96 M insns, PEN-F 8.87 M).
- `xm.py` / `run.py` (wrapper `r.sh`):
  - `m:` / `r:`: align.py-style k-gram (K=6) diagonal voting on coarse shapes, then difflib refinement. Reports `sup` (support votes), `fr` (fine ratio) and `ex` (whether the site's opcode matches).
  - `s:` / `S:`: xmatch.py-style shape regex. `s:` is strict; `S:` keeps only the first opcode byte.
  - `c:`: caller vote. It maps up to 40 OM-3 call sites of a function and counts which PEN-F targets the mapped calls hit.
  - `i:`: immediate/constant search. `x:`: xref search. `l:`: short listing.
- Data-xref helpers:
  - `words.py`: find or dump u32 words (addresses only).
  - `vtab.py`: maps the facade vtable slot by slot.
  - `recs.py`: finds editor records.
  - `sectab.py` / `itemtab.py`: table hunts.
  - `fstart.py`: finds function starts and their callers.
- Confidence labels:
  - **H**: two or more independent confirmations, for example align plus a caller vote, a unique shape, a constant, or a table slot.
  - **M**: one strong signal plus structure.
  - **L**: weak or ambiguous.
  - **none**: no counterpart found.
- All findings are [static] unless marked [spec].

## Sanity anchors

| OM-3 | What | PEN-F | Score | How | Note |
|---|---|---|---|---|---|
| 0x60518381 | HSL colour builder | **0x604f7272** | sup 65, fr .878, ex | align + xref | Its only caller is 0x604f7506. H |
| 0x60518615 | builder call (hook) | **0x604f7506** | sup 6, fr .544, ex | align, known | `call 0x604f7272,[d2,d3,a2,a3],96` (same frame 96). H |
| 0x6051861a | resume | **0x604f750b** | sup 6, ex | align, known | H |
| 0x603f0111 | caduceus `sget` (stub `exthu d0; call 0x603f15b6,…,20`) | **0x602b9da3** (stub → 0x602bad44) | sup 58, fr .689; caller vote 15/23 | align + caller vote | **Not 0x602f024a.** H |
| (reverse) 0x60419315 | OM-3 counterpart of PEN-F `setting_get` | PEN-F **0x602f024a** | sup 68, fr .878; reverse caller vote 30/39 | reverse align + caller vote | The brief's pairing 0x603f0111↔0x602f024a is two different getter families. `aget` 0x603f039d ↔ 0x602b9f84 (same stub table). H |

## (1) Picture Mode list / settings / editor

| OM-3 | What | PEN-F | Score | How | Note |
|---|---|---|---|---|---|
| 0x60b8798b | settings-manager call in SetValue (`.hook_set`) | **0x6073659d** `call 0x6075fbed,[d2,d3,a2],16` | struct | xref + epilogue | The manager has exactly 2 callers on each side. Same `cmp 1,d0; beq; mov 128,aN` after the call. Arguments differ: PEN-F d0 = id (40,sp), d1 = value (36,sp), a0 = (4,a3), and no a1 "mode". H |
| 0x60bb528f | settings manager | **0x6075fbed** | caller vote 1/1 | xref | No `cmp 4508` special case on PEN-F. It is the 4th of four sequential setter calls (0x6075fcbc/fc8f/fc62/fbed). H |
| 0x60e57474 | facade vtable (56 words) | **0x609a4660** (41 words) | 35 slots align: OM-3[i] ↔ PEN-F[i−1] | data xref + align | Referenced from 0x6073564c / 0x6073566c (OM-3 refs 0x60b869d2/f2). This confirms OM-3's extra slot [1]. H |
| 0x60b86de7 | GetValue (+12) | **0x607359ef** (slot +8, word 0x609a4668) | sup 42, fr .878 | vtable + align | PEN-F GUI code calls it as `mov (8,a2),a2; calls (a2)`. H |
| 0x60b8781f | SetValue (+4) | **0x607363b3** (slot +0, word 0x609a4660) | (align went elsewhere: 0x606f5e49 lies in a different table) | vtable + it holds the manager call | PEN-F has no separate slot. Slot [0] contains the setter chain and manager call. M |
| 0x60b86a01 | selectable (+40) | **0x6073567b** (word 0x609a4684) | sup 45, fr .811 | vtable + align | H |
| 0x60b86e44 | GetDefault (+156) | **0x60735a4c** (word 0x609a46ec) | sup 58, fr .878 | vtable + align | H |
| 0x60b86e09 / 0x60b87031 | count / value-by-index | **0x60735a11** (0x609a4678) / **0x60735c39** (0x609a467c) | sup 47 / 67 | vtable + align | H |
| 0x60b8696a | facade singleton getter | **0x607355e9** | caller vote 35/35 | caller vote | H |
| 0x61223ef7 | COLOR editor Up (record +12) | **0x60cb0684** | records 3/11 slots exact | record xref | PEN-F records are 0x60f6df6c/a4/dc (keys 0x13b2–0x13b4, i.e. **three** COLOR profiles), plus 0x60f6df34 (key 0x13a8).<br>Other slots: init 0x60cb025c, child_get 0x60cb03cf (exact), Down 0x60cb08e5, L/R 0x60cb0bbb/0x60cb0feb, event 0x60cb190e, INFO 0x60cb1c5e.<br>Plain align confused Up and Down (both landed on 0x60cb0a62). M |
| 0x611b20ea | child/bar refresh | **0x60c7f19b** | caller vote 32/35 | caller vote | H |
| 0x611b201b | bar "stop at ends" (`.hook_stp`) | **0x60c7f124** | sup 30, ex | align + identical shape | Bar field +116 → **+104**. Id table 0x6152d520 → **0x60f48714**. H |
| 0x611b21e8 | bar list order (`.hook_rev`) | ~0x60c81c14 | sup 30, interp | align | The id-table loop end matches (322 → 192 ids), but PEN-F has no id-469 branch. L |
| 0x610f56a6 | string getter (`.hook_str`, fl_tt) | **0x60bcb228** | caller vote 29/37, ex | caller vote + shape | Language index function 0x610f56bd → 0x60bcb23f. H |
| 0x610f5611 | picture-id lookup (`.hook_ic`) | **0x60bcb1eb** | caller vote 13/14 | caller vote | H |
| 0x611b32ae | Picture Mode list builder (GetValue return compared in fl_get) | **0x60c7fc35** (in handler 0x60c7fb93) | sup 18; twin 0x60c7f898 ties | align + handler table | OM-3 handler 0x611b2fc4 is listed as {fn, item 205} at 0x6152def4. PEN-F 0x60c7fb93 is also {fn, 205} (0x60f48a2c).<br>Twin functions 0x60c7f779 / 0x60c8114d have the same shape. M−/L |
| 0x611d08f4 | row left cell (GetValue return) | none | sup 11, fr .28 | — | The Picture Mode row/slider GUI (0x611c–0x611d) has no counterpart. none |
| 0x611c3cb5 | held-OK reset end (`.hook_rsp`) | none | sup ≤ 20, interp; callers also unmatched | — | none |
| 0x611d1837 | row check return after "COLOR changed?" | none | sup 3 | — | none |
| 0x6129ba07 | "COLOR profile changed?" (`.hook_pmod`) | none | strict + loose shape 0 hits; align lands on an unrelated cmp/beq cascade (0x61027d18) | — | The OM-3 version tests picture modes 54/55/56/64 over 4 tables. PEN-F has 3 COLOR records, and its equivalent was not found. none |
| 0x611bd814 / 0x611bd8fd | Picture Mode column builder (pm_color) | 0x60c7f779 ? | sup 7, ex | align only | Handler for PEN-F item 908. Unconfirmed. L |
| 0x611d1041, 0x611d10fb, 0x611d1035, 0x611d16b4, 0x611d1725, 0x611d07a4, 0x611c3709, 0x611d0be0, 0x611d1982 | slider/readout/paging hooks (v0.23 rows) | none | sup ≤ 10, interp | — | Newer GUI layer than the PEN-F's. none |
| fl_* film-list hooks | fl_get/fl_set/fl_sel use facade slots; fl_tt/st_get the string getter; ic_get the picture lookup; fl_pmod pmod; rs_pos the reset end | see rows above | — | — | Facade, string and picture lookups are portable. The list/row/pmod/reset sites are not. |

## (2) Image pipeline hooks

| OM-3 | What | PEN-F | Score | How | Note |
|---|---|---|---|---|---|
| 0x605197d7 | tone hook (`mov d3,a0; call 0x60518fa4,…,56`) | **0x604f85ef** `mov d3,a0; call 0x604f7d50,[d2,d3,a2,a3],76` | stage list 0x604f85dc.. | align + stage structure | PEN-F has an extra first stage (0x604f698e), then:<br>• COLOR stage 0x604f747f (holds the builder call)<br>• lum-LUT 0x604f7c76 (= OM-3 0x60518db2)<br>• tone_next **0x604f7d50** (= 0x60518fa4: sup 19, ex)<br>• chroma 0x604f83f1<br>Raw align picked 0x604f85e8, one stage early. Frame is **76**, not 56. H |
| 0x60555e50 | Art Effect → job flags (`.hook_fx`) | **0x60535711** | strict shape unique (24/30 exact bytes) + align sup 43 | shape + jump table | Same flags: Soft Focus 0x80, Pin Hole 0x400, Frame 0x8000, White Edge 0x2000, Star 0x40, Diorama 0x100/0x200. Jump table 0x6063e618 (OM-3 0x606e5f88).<br>Art id at capture **+19323** via (124,a0) (OM-3 +38225 via (20,a0)). Converter 0x60555e47 → **0x60535708** (1 caller 0x60531e53). H |
| 0x6046b8bb | LV Art Effect gate (picture mode ≥ 100) | none | its Art switch tail aligns onto the capture converter (0x605356d1..) | — | No `cmp 100` gate found near. none |
| 0x605048c1 | Soft Focus weight getter (`.hook_wt`) | none | strict/loose shape 0 | — | The preceding function aligns (0x60504811 ↔ 0x604ea013, sup 22–29), but the next PEN-F function (0x604ea0b8) is different.<br>Key 0x01010065 appears on PEN-F only at 0x604c1de6 (counterpart of OM-3 0x604b39f9). none |
| 0x603c8038 | NR read #1 (key 38681) | none | — | constant | Key 38681 occurs on PEN-F only at 0x60253657 (capture) and 0x60af3e99 (UI). none |
| 0x603e7891 | NR read #2 (capture +37674) | **0x60253660** `call 0x600750ee,[d2,d3],12` | align top, ex; key 38681 | align + constant | Result stored `movbu` at capture **+18582**. H |
| 0x603e767f | Sharpness read (key 33049, capture +37648) | **0x60253546** | key 33049; next read 33089 on both | constant + structure | Result stored at capture **+18562**. Raw align picked the following 33089 call (0x6025355c). H |
| 0x604955f1 | request config `call SEL` (`.hook_cl`, grain) | **0x604aaad1** `call 0x604fb7b8,[a2],8` | strict shape unique + align sup 31 | shape + align | SEL 0x6052cf39 ↔ **0x604fb7b8**. Register list and frame differ ([a2],8 vs [d2,a2],12). H |
| 0x60457982.. | WB fine-tune reads (wb_get: keys 34041/38521) | **0x6054f1e6** (+0x6054f33b.., 8 sites per key) | sup 31, ex | align + constant | Keys are shared. Results go to capture +18640. H |
| (key) 63153 | COLOR profile number key | present at 0x60253b6a, 0x6083e750, 0x60af3f4f, 0x60afdf93 | — | constant | Same profile key exists. [spec] Values likely 1..3 on PEN-F. |

## (3) File I/O, heap, half-press, sections

| OM-3 | What | PEN-F | Score | How | Note |
|---|---|---|---|---|---|
| 0x60024068 | malloc | **0x60023459** | sup 14, fr .756; caller vote 16/19 | align + caller vote | Size classes 128/2048 (OM-3 192/2112). H |
| 0x6002409a | free | **0x60023498** | caller vote 16/23 | caller vote + prologue | Pool range check 0xa1221fc0..0xa122a540. Align's 0x600233fc is a sibling free for another pool, rejected. H |
| 0x608d4d22 | fopen | **0x60599595** | sup 18; caller vote 28/31 | both | H |
| 0x608d4d2b | fclose | **0x6059959e** | caller vote 16/19 | both | H |
| 0x608d4fb1 | fseek | **0x60599804** | sup 41; caller vote 20/22 | both | H |
| 0x608d4f47 | ftell | **0x6059979e** | sup 44; caller vote 3/3 | both | H |
| 0x608d4eb7 | fread | **0x60599715** | caller vote 20/22 | caller vote | Same prologue as fwrite. Align alone was ambiguous. H |
| 0x608d4da9 | fwrite | **0x60599615** | caller vote 21/25 | caller vote | OM-3 order (fwrite < fread) is kept. H |
| 0x6003193e | get_tid | **0x60031be2** | sup 71, fr .889; caller vote 31/37 | both | Same `(0x8050)` global. H |
| 0x60063380 | profile/property getter (nf_get) | **0x600750ee** | sup 69; caller vote 12/15 | align + caller vote + constants | Called with the same keys (33049, 38681, 34041, 38521, 63153). H |
| 0x60415216 / 0x6041521b | half-press hook / resume | **no site**. Enclosing function 0x60415111 ↔ **0x602ed4c4** | caller 0x60af1445 ↔ 0x606bbe45 sup 75, ex; call sequence aligns | caller + call sequence | PEN-F has no event 256/257 → callee block. The analogous point is **0x602ed5aa** (after `call 0x602eef46`). A new hook would be needed there. Partial |
| 0x60415343 | half-press callee (trig) | none | align → 0x602ed68a, rejected (generic utility with 22 callers) | — | none |
| 0x60045ed5 | section loader | **0x600421e1** | structure | xref chain | Both call the section-end switch (0x60045e6c ↔ **0x600420c1**, 3 callers each). Table stride 12.<br>PEN-F reads the section id from global 0xa1c583fc instead of d0. M |
| 0x60029b28 | section table | **0x60026d7c** | 7 entries | data scan + xref (0x600422ae reads 0x60026d84, as OM-3 0x60046095 reads 0x60029b28) | Layout {start, flash, start} with flash = runtime − 0x1fc81000. OM-3 uses {dest, flash, flag}. M |
| 0x60045e9c | section-6 end word | section ends are immediates in 0x600420c1:<br>s1 0x601cb000 (@0x600420e5), s2 0x60428000, s3 0x6069b800, s4 0x60a50000, s5 0x60fdc800, **s6 0x610f2000 (@0x6004210d)**, s7 0x61100000, s8 0x6115b800 | — | structure | s1 end 0x601cb000 agrees with code_space/audit.json.<br>[spec] The s6 copy end 0x610f2000 is below the table's 0x61100000. Whether caduceus's "raise the end" trick applies is unverified. M− |

## Match rate
- The brief's list has 35 sites:
  - 20 matched **H** (57%).
  - 6 matched **M/M−**: SetValue, Up, section loader, section table, end word, list builder.
  - 1 partial: half-press (function matched, site absent).
  - 8 none: LV gate, Soft Focus weight, NR1, half-press callee, "COLOR changed?", row left cell, reset/scroll, row check.
  - Some counterpart for 26/35 (74%).
- Of the 13 extra editor.ld UI hooks: 3 H (str, ic, stp), 1 L (rev), 9 none.
- The strict xmatch-style regex hit uniquely only for fx and s_cl. Everything else needed k-gram alignment, caller votes, constants or table xrefs.
- The raw align top pick was wrong or off by one instruction/stage at tone, Sharpness, free, half-press callee, SetValue, Up and the getter anchor.
