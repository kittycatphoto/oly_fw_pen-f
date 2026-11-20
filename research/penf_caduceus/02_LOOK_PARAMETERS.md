# PEN-F 3.1 (build 3101): which caduceus-style "film look" parameters can work, and where they hook in

Research notes from agent B, 2026-11-11. Read-only. Addresses are PEN-F CPU addresses (decoded main + 0x60021020).

Evidence labels:
- **[static]**: I read the code or data on the PEN-F image (full listing `oly_fw_analysis/generated/livend/main.dis`, plus table dumps).
- **[emu]**: I ran original PEN-F code in fishcu's MN103 emulator with synthetic fixtures. My scripts are in `scratchpad/agentB/scripts/`. The work-list matrix output is in `scratchpad/agentB/jobs_matrix/audit.json`.
- **[pub]**: from the caduceus-om3 docs (local checkout v0.24.1, plus the coordinator's v0.25–v0.26.2 notes) or fishcu's PEN-F docs. I did not re-check these.
- **[spec]**: my own inference.

Nothing here was tested on a camera.

---

## 0. Key facts established in this pass

1. **Setting keys are the same across bodies.** The PEN-F id-to-key table is at `0x603fa158` (u32 `{u16 key, u16 index}`). id 7 = Sharpness `0x8119`, id 61 = Shading Comp. `0x8c21`, id 143 = Noise Filter `0x9719`, id 912 = COLOR profile `0xf6b1` (the OM-3 profile getter key 63153), and the WB A-B and G-M arrays are `0x84f9` and `0x9679` (the OM-3 keys 34041 and 38521). The PEN-F key getter is **`0x600750ee`** (d0 = key, d1 = array index, a0 = 0), the counterpart of OM-3 `0x60063380`. [static]
2. **The development stage list is at `0x604f8543`** and has the same shape as the OM-3 list: matrix `604f45a6` → RGB gamma `604f6083` → (bypass predicate `604f2a64`) → 6-axis `604f55de` → chroma gain `604f698e` → 12-sector HSL `604f747f` (fishcu's hook is inside it at `0x604f7506`) → **tone `604f7c76` (call site `0x604f85ea`)** → chroma suppression `604f7d50` → tint `604f83f1` (call site `0x604f85f8`) → `604f852d` → `604f54ca`. [static]
3. **On the PEN-F, MONO's grey is made by one control word in development: the tint word at output+0x20c+76.** Key 11 gives `0`. Key 12 gives `0x00808001` (Cb = Cr = 0x80 forced) in every development stage, 0, 0x901 and 0x902. With a synthetic request this was the **only** key-dependent difference in the full dev configuration: matrix, 6-axis, chroma gain and tone pointer were all equal. [emu]
4. **MONO's grain is a separate combiner pass, not part of development** (this differs from OM-3). Stills use mask pass `0x0900`, then image+grain pass `0x0901` (combiner 31, gains 110/300/600), then a late kind-3 `0xf005` shading pass, then the final pass. The non-still route (job+12204 = 1) is one `0x0902` pass with combiner 32 (gains 50/75/100). Every grain control is gated on **key 12**: with key 11, the mask tone, the combiner selector and the gain all fall back to their defaults. [emu: reproduced fishcu's matrix of 34 cases, plus my key-11/12 × stage runs]
5. **The PEN-F Grainy Film ART filter has its own texture route.** Its key is `0x01010068`/`0x01020068` (I/II); see §(a2). [static+emu]
6. **The PEN-F Cross Process filter uses three different R/G/B gamma curves.** COLOR uses one curve for all three channels. The pointers are at output O+0x1430/0x1434/0x1438. [emu]

---

## 1. Parameter table

"Per-profile" means it is already one of COLOR1–3's 18 stored settings. "Global" means a stock setting that is not per profile, so a per-look value needs a getter override. Sizes are rough [spec].

| Look parameter | PEN-F status | Setting id / hook address | Route | Rough code | Evidence |
|---|---|---|---|---|---|
| Saturation, 12 sectors | **Stock per-profile** | 931–966 (−5..+5) | stock COLOR builder | 0 | [static][pub fishcu] |
| Hue / Luminance, 12 sectors | **Done** (fishcu HSL, camera-proven) | hook `0x604f7506`→`0x604f750b`; job+14920 | capture, record, compact and RAW-edit transport | (exists) | [pub] |
| Tone: Highlights / Shadows / Midtones | **Stock per-profile** | 967–975 (−7..+7 ×3) | tone builder `604f75e5` | 0 | [static] (names inferred from list shape) |
| Contrast | **Stock per-profile** | 916–918 (−2..+2) → effective id 8 (`0x82a9`), capture+18566 | | 0 | [static] |
| Sharpness −2..+2 | **Stock per-profile** | 913–915 → id 7 `0x8119`, read at `0x60253540` → capture+18562 | `604f3405` index = baseline + value, clamped 0..10 | 0 | [static] |
| Sharp "Off" (−5) | **Needs hook**, and full off needs more | getter override at `0x60253540` (RAW edit `0x60af3ec1`) | index 0 of table `0x60619ade` = **64, not 0** (COLOR at 0 = 256, at −2 = 160). A look can reach ≈¼ gain. True zero needs a gain/coring change in `604f3ba1` (fishcu proved 0 reaches the register). | ~40 B + shared stub | [static][pub fishcu] |
| Shading (creative vignette) | **Stock per-profile** | 1111–1113 (−5..+5) | COLOR: combiner 33 inside development | 0 | [static][emu] |
| Lens shading comp. off (VigFix) | **Global** (id 61, {0,1}) → needs hook | reads of key `0x8c21` at `0x60247cb5`, `0x6024cf88`, `0x60258083`, `0x602582f0`, `0x6054f652` | getter override | ~40 B + 5 sites | [static] |
| Noise Filter Off/Low/Std/High | **Global** (id 143, stock list {−2,−1,0,+1} = Off/Low/Std/High, so High is already stock) → needs hook | key `0x9719` reads: **`0x60253657`** (capture → +18582), `0x60af3e99` (RAW edit) | getter override | ~40 B, 2 sites | [static] |
| WB shift A-B / G-M per look | **Global, per WB preset** (ids 39, 91–96, 132–138, 144–145, 212–215, 338–339, 574–577, 1161–1167, 1186–1192; ±7) → needs hook | getter calls with key `0x84f9`/`0x9679`: capture `0x6054f1dd..0x6054f540` (5 pairs → capture+18640/18642), compact/live view `0x6055741c`/`0x60557431`, `0x60567dcc`/`0x60567de4`, RAW edit `0x60af5513`/`0x60af5527` | additive override, as in OM-3 `wb_get` | ~100 B + ~9 call sites | [static] |
| Blacks / Whites (tone ends) | **Needs hook** | tone call site **`0x604f85ea`** `call 0x604f7c76,[d2,d3,a2,a3],28` (7 B); LUT pointer O+0x20c+**0x1230**, job-owned buffer +**0x1234** (256 × u16); rebuild gate C+56 & `0x2e8063e`; external curve at request+960 | port of OM-3 `tone` (0x605197d7) | ~450–600 B | [static] |
| Film Grain on COLOR | **Needs hooks.** Three candidate routes (§a). | `0x604c58a0` work-list key, `0x604fb7b8` selector, `604f75e5` mask tone, `604ea2ba` gain, or the Grainy Film texture route | MONO combiner 31 path with colour kept, or texture route | 200–500 B | [static][emu] |
| Grain size | **Not possible** in stock engines | no radius control in combiner 31 or 32; Grainy Film texture has a fixed scale | | — | [pub fishcu][spec] |
| Split toning (shadow / highlight hue) | **Needs hook** | RGB-curve selector **`0x604f2a94`**, call site `0x604f60d2` (7 B); outputs R/G/B pointers → O+0x1430/0x1434/0x1438 | bend the three curves (OM-3 v0.26 design) | ~150 B + 1.5 KB curve buffers | [static][emu] |
| Soft Focus / Glow | **Needs hook** (Art Effect flag path exists for any key) | flag 0x80 in job+16. Converters: preview/recview `0x60524f8a` (capture+19323 = Art Effect id from setting key `0xf5d1`, read at `0x60253b16`); record converter `0x605356e2..0x605357b7`. Work list tests 0x80 for every key. | flag OR for COLOR plus a weight override | ~80 B; weight site not located | [static] |
| Clarity (Soft Focus with weight > 1024) | **Needs hook** and the weight site | Soft Focus weight: probably combiner builder `604ea2ba` (cases near `0x604ea5a8`/`0x604ea5e9` hold 600/424) | | ? | [spec] |
| Coloured glow | **Not attempted** (caduceus failed on OM-3) | | | — | [pub] |
| Art Effects (Star, Pin Hole, White Edge, Frame, Diorama, Shade) | **Needs hook** (same flag path) | jump table `0x60637644` (recview) / `0x6063e618` (record): 0x80, 0x400, 0x8000, 0x2000, 0x40, 0x100/0x200, 0x800/0x1000 | | in the flag hook | [static] |
| White frame (custom) | Needs frame-layer data patch (caduceus OM-3 comp 2) | not mapped on PEN-F | | data | [pub] |
| Highlight roll-off | Same hook as Blacks/Whites (shape the top of the tone LUT); or the rational shoulder in SHADING.md | `0x604f85ea` | | in the tone hook | [spec][pub fishcu] |
| Colour filter / toning (as in MONO) | **Not for COLOR without hooks.** Tint word +76 is the toning control (bytes {flag, Cb, Cr}). It could carry a global COLOR tint but not split toning. | `604f83f1` / `604f82c2` | | ~40 B | [static][emu] |

---

## 2. Detailed answers

### (a) Can COLOR photos get the camera's grain? What happens to chroma?

**COLOR and MONO job routes on the PEN-F** [emu, `jobs_matrix`, 34 cases]:

| Job | Requests |
|---|---|
| COLOR key 11 (any grain byte, shading 0 or −5) | **one** kind-0 development (stage 0): combiner 0, or 33 with shading. The grain byte is packed into the request (request byte +1088 = 3) but nothing consumes it, because combiner 31/32 need stage 0x0901/0x0902 and context key 12. |
| MONO key 12, stills | `0x0900` mask (tone LUT `0x60610742`) → `0x0901` image + grain (combiner 31, reads the mask) → kind-3 `0xf005` (combiner 33 only if shading ≠ 0, but the pass always runs) → kind-3 final |
| MONO key 12, job+12204 = 1 | `0x0902` (combiner 32, gains 50/75/100) → `0xf005` → final |

The work list is selected by hash table `0x60626dc0` (stored key = key − 11; stored `0x1` = key 12 → handler **`0x604c5c46`**). The handler sends a MONO job to the plain COLOR entry `0x604c4c84` (no grain) when the format bits at job+20 are 0x10, 0x20 or 0x40, or when (&0xf00) == 0x100. It sends the job to `0x604c4c84` with callback `0x604c8471` (the 0x0902 single pass) when job+12204 ≠ 0. Otherwise it uses mask `0x604c81db` + image `0x604c82eb`. [static]

job+12204 is set by the job constructor (`0x604c1d93..0x604c1dc5`) from classifier `0x604fbac5(type halfword, byte)`. Classes 4–8 give 1; still type 0x1000 gives class 0, so 0. So the single-pass 0x0902 grain is the **non-still** route (live view or movie, most likely) [static; the label is spec].

**What makes MONO grey on the PEN-F:** in the development stages, `604f83f1` writes tint word O+0x20c+76 = `0x00808001` for key 12 and 0 for key 11 [emu]. The late kind-3 image route (format 0x0302) sets tint 0 [emu, fishcu control reproduced]. The mask route (0x03a4) forces `0x00808001` [pub fishcu]. The grain itself is luma-only in the desktop model, and Cb/Cr pass through [pub fishcu].

Two more key-12 traps that the synthetic fixture cannot show [static]:
- The 12-sector HSL and saturation selector `604f747f` takes the COLOR path only when **request key == 11** (`0x604f74ee cmp 11`). Key 12 loses COLOR saturation and fishcu's H/L.
- The tone curve selection `604f75e5` and tint `604f82c2` are keyed by picture mode.

**Three routes to colour grain on the PEN-F:**

- **(a1) MONO combiner-31 route with key 11 kept** (recommended to try first) [spec, built on static+emu facts]. Mark the COLOR still job. Four overrides follow:
  1. In the work-list selector, send marked key 11 to handler `0x604c5c46`. The dispatch is at `0x604c58a0..0x604c58e1`; a 7-B hook before the hash lookup works.
  2. In mask-pass tone selection `604f75e5`, stage 0x0900 must return LUT `0x60610742` (with key 11 it returns the default `0x605fdd38` [emu]).
  3. In combiner selector `604fb7b8`, a marked request at stage 0x0901 must return 31 (with key 11 it returns 0 [emu]).
  4. The grain builder `604ea2ba` must produce the gain (with key 11 the gain word is the default `0x04000400`, not 110/300/600 [emu]). Run it with context key 12 for the builder only, as OM-3's `xb_h33` trick did.

  The colour stages (HSL, tone, tint 0, WB) stay COLOR because the requests keep key 11. Shading moves to the late `0xf005` pass (combiner 33 on a 0x0302 image; tint 0 there [emu]). Whether combiner 33's own config greys a key-11 image is **not known**: on OM-3, combiner 33's MONO config made the image grey [pub]. Cost: about 96 MiB of buffers per shot instead of one pass (mask 20.2 MB + 2 × 40.3 MB) [pub fishcu], and 3 more requests per shot.
- **(a1') MONO job (key 12) with tint forced to 0.** This needs three overrides instead: tint `604f83f1`/`604f82c2`, the HSL key test at `0x604f74ee`, and the tone selection. It also changes key-dependent tone and contrast. Riskier for colour fidelity [spec].
- **(a2) Grainy Film texture route** (the PEN-F analogue of caduceus v0.25) [static+emu]:
  - Work list for key `0x01010068`/`0x01020068` (table A `0x60626ec0`, handler `0x604c554d`), stills: `0x604c4a47` (texture offset := 0) → `0x604c8be3` with request callback **`0x604c8b6a`** → `0x604c8f5c` with callback `0x604c9168`.
  - The callback copies a texture image descriptor from **job+13732** into the request's secondary input, at offset `job+13728 & mask`, and sets stage **0x0100**.
  - Selector `604fb7b8` then picks **combiner 1** for key 0x0101/0x0102_0068 at stage 0x0100 [emu].
  - The texture descriptor comes from a resource cache, `0x604d8982`, called at job preparation (`0x604c670e → 0x604c6719`) [static].
  - Grainy Film's **monochrome conversion and its contrast curve are in the separate kind-3 stage `0x0101` pass**: tint `0x00808001`, tone `0x6060d542` (I) / `0x6060e542` (II) [emu]. The `0xf005` route gives tint 0.
  - For non-still classes 4–7 the work list uses `0x604c4a25` instead, which re-seeds the texture offset with xorshift 13/17/5 each job (animated grain). The 0x100/0x40 format types get no texture [static].
  - **For COLOR:** run the texture dev pass (stage 0x0100, combiner 1) on a COLOR job and skip the 0x0101 mono pass. That needs the texture loaded at job preparation, the selector to return 1 for a marked key-11 request, and the combiner-1 builder to accept a COLOR context.
  - Grainy Film has no Low/Med/High. Strength would come from the combiner-1 config words, which are not mapped [spec].
  - Combiner 1 and combiner 33 (shading) cannot share one pass, so grain + shading needs a second pass [spec].
  - **Untested in emulation:** the GF dev pass itself faults in my fixture (missing texture and art-cache objects).

  Fast, in one pass, and it previews in live view (classes 4–7) [spec]. **Chroma:** the texture blend's effect on Cb/Cr is unknown. OM-3's v0.25 result suggests colour survives [pub].
- **(a3) CPU grain** (caduceus-ep7 / OM-3 CPU route, 3–5 s per photo) [pub]. Always possible in principle, but needs CPU access to the image buffer on PEN-F. Not mapped.

### (a4) Risk of a second development in RAW+JPEG (caduceus v0.26.2 freeze)

The PEN-F develops one shot several times [static/pub fishcu]:
- preview/recview converter `0x6052010f` (call sites `0x6051c78d`, `0x6051d4e9`);
- a separate **recording** converter `0x60531fdb` (its Art Effect/flag copy is at `0x605356e2..0x605357b7`, distinct from the recview copy at `0x60524f8a`);
- the RAW-edit preparers `0x60af2edc`/`0x60af3c7f`;
- compact (live view) jobs on CPU2.

Any look state kept as a one-shot global flag, as OM-3's `xb_gt` was ("stays set until the next capture"), will be consumed or reset by the first development and missing or stale in the next. RAW+JPEG and playback RAW edit are the obvious triggers. **Recommendation** [spec]: carry every per-shot look value with the capture owner and the job, the way fishcu's H/L transport does (45 acquisition rows, extended job member, all 16 operation records). Never use a global. Also budget for the MONO-route buffers (a1) in RAW+JPEG and sequential shooting. The reservation mode at `0x60549311` reserves 8 of 24 slots [pub fishcu], and the extra ~96 MiB per shot is unqualified.

### (b) Blacks / Whites: the PEN-F tone curve builder

The counterpart of OM-3 tone hook `0x605197d7` is **PEN-F `0x604f85ea`: `call 0x604f7c76,[d2,d3,a2,a3],28`**, 7 bytes, in stage list `0x604f8543`. In `0x604f7c76` [static]:
- If request+960 ≠ 0, use the externally supplied curve (art override); its pointer goes to O+0x1230 (output = C+12).
- Else, if C+56 & `0x2e8063e` (the rebuild test; OM-3's is C+60 & `0x4134063e`), build or select through `0x604f7c18 → 0x604f75e5` into the **job-owned buffer O+0x1234**, pointer at O+0x1230.
- If `0x604bdd21(req+948)`, copy to O+0x1234 and post-process with `0x604be08d` (flag request+1065 bit 7).
- The default curve pointer is `0x605fdd38` (`0x604f7c66`).

The LUT is 256 × u16 and is uploaded by `0x604b58c4` [pub fishcu]. A Blacks/Whites hook copies the selected curve into O+0x1234 when it is not there already, remaps it, and sets the pointer. Gate: key 11, plus key 12 marked when combined with (a1'). This is the same shape as OM-3's port, so the OM-3 `tone` routine should transfer with new offsets: O+3828 → O+0x1230, O+3832 → O+0x1234 [spec]. **No conflict with HSL:** fishcu's hook is inside `604f747f` at `0x604f7506`. The tone call site is a separate stage-list entry [static].

### (c) WB shift per look

Stock WB compensation is **global, per WB preset**, not per COLOR profile. It is two key arrays: `0x84f9` A-B and `0x9679` G-M, about 20 entries each, value list ±7 (e.g. id 91's list is ±7) [static]. Capture reads happen in the WB-mode switch at `0x6054f1d1..`: d1 = preset index, results go to capture+18640 (A-B) and +18642 (G-M). Live view reads index 0 at `0x6055741c`/`0x60557431` into the compact slot. More reads are at `0x60567dcc`/`0x60567de4` (→ `0x61bcab09`/`0x61bcab0a`) and in RAW edit at `0x60af5513`/`0x60af5527`. A per-look additive shift = override getter `0x600750ee` at these ~9 call sites (7-B `call` each), adding the look's value when the effective picture mode is COLOR, then clamping to ±7 [static/spec]. OM-3 needed 12 sites plus AWB fine-tune keys [pub]. The PEN-F id table has no `0x1ce9`-style AWB fine-tune keys [static].

### (d) NR / Noise Filter and Sharpness Off

- **Noise Filter:** id 143 key `0x9719`, stock list Off/Low/Standard/High, global. The capture read is at **`0x60253657`** (→ capture+18582 byte); RAW edit at `0x60af3e99`. These are the only two immediate key loads in the image [static]. A per-look value = a getter override at those two sites. caduceus's "new High" is stock on the PEN-F. A level above High is not possible without NR-table work [spec].
- **Sharpness:** see the table. The index clamp is at `0x604f3b2d..0x604f3b37` (0..10). Baselines are at `0x60619ad2`, the gain table at `0x60619ade` = 64…256. So the PEN-F's lowest reachable gain is 64, and "Off" ≠ 0 [static]. A real off needs a different packed gain in `604f3ba1`, or a data change to the shared table entry, which also hits other modes [pub fishcu].

### (e) Split toning through per-channel gamma curves

**Yes. The PEN-F Cross Process uses separate R/G/B curves.** Running `604f6083` [emu]:
- key 11 and key 12 both put the same curve pointer `0x605fdf38` in O+0x1430, O+0x1434 and O+0x1438;
- key `0x0101006b` (Cross Process I) puts three different curves, `0x605fef38`, `0x605ff138` and `0x605ff338`; `0x0102006b` (II) also differs;
- key `0x01010070` uses the plain curve;
- Cross Process also changes a derived table at O+0xa34..0xdff, which is rebuilt inside the stage from the selected curves.

The selector is **`0x604f2a94`**, called at `0x604f60d2` (`call 0x604f2a94,[a2,a3],12`, 7 B), writing three pointers to (64/68/72,sp). The stage then optionally builds modified copies into **job-owned 3 × 512 B at O+0xc24 / +0xe24 / +0x1024** (`604fc3e8`, when (61,sp) is set) [static].

A split-toning hook belongs right after the selector returns: point R/G/B at look-bent copies. The stock stage then derives its tables from them, which avoids patching the O+0xa34 table [spec]. Buffers: 1.5 KB per concurrent context. Still and compact jobs can overlap on different CPUs, so plan two sets or use the O+0xc24 area if it is unused when (61,sp) = 0 (unverified) [spec]. The OM-3 v0.26 claim of "photos and live view" [pub] fits the PEN-F, because the compact path uses the same stage list [static], but this is not verified on the PEN-F.

### (f) Soft Focus / Glow

- **Art Effect id:** capture+19323, from setting key `0xf5d1` (read at `0x60253b16`). The converters map it to job flags with the OM-3 values (0x80 Soft Focus, 0x400 Pin Hole, 0x8000 Frame, 0x2000 White Edge, 0x40 Star Light, 0x100/0x200 Diorama, 0x800/0x1000 Shade). If capture+18596 or +18597 ≠ 0, they OR in `0x200000` (MONO filter/grain route). This happens in both converters: `0x60524f8a` (recview) and `0x605356e2..0x605357b7` (record) [static].
- **No picture-mode gate between the converters and the flags, and the default work-list path (`0x604c5d33..`) tests 0x40/0x80/0x300/0x400/0x1800 for every key** [static]. So a COLOR job carrying 0x80 should schedule the Soft Focus passes. Stills and non-still classes 4–7 use different entry sets [static].
- **Cheapest hook:** override the `0xf5d1` getter at `0x60253b16` (capture) and in RAW edit (`0x60af3f2f` writes +19323), returning the look's effect for COLOR. Or OR the flags in at the two converters [spec].
- **Glow strength and Clarity:** need the Soft Focus weight site. OM-3's weight getter (`0x605048c1`: key 0x01010065 → level, else 600) was **not found** on the PEN-F. The candidates are combiner-builder cases in `604ea2ba` with 600/424 constants (`0x604ea5a8..0x604ea627`) [spec].
- **Coloured glow:** not possible per caduceus [pub].

### (g) Live view vs capture

| Feature | Live view | Basis |
|---|---|---|
| Saturation, tone, contrast, sharpness, shading (stock) | yes (stock behaviour) | |
| H/L (fishcu) | yes, camera-proven | [pub] |
| Tone hook (Blacks/Whites), split toning | very likely yes: the compact jobs go through the same `0x604c2447` dispatch and the `0x604f8543` stage list | [static/spec] |
| WB shift | yes, if the compact read `0x6055741c`/`0x60557431` is also overridden | [static] |
| NR / VigFix / Sharp Off | capture-only reads mapped; live-view effect not expected or not needed | [static] |
| MONO grain (a1) | live view uses the 0x0902 single pass (combiner 32) through job+12204 = 1, which needs its own override; the preview grain is weaker (50/75/100) | [static+emu] |
| Grainy Film texture (a2) | classes 4–7 use the animated-offset texture route, so live-view preview is plausible | [static] |
| Art Effects | stock has separate class 4–7 entries; where live-view job flags are set for COLOR was **not located** (OM-3's gate `0x6046b8bb` counterpart not found) | [static gap] |
| Creative shading | the live-view mapping is separate (`602fc73a`) | [pub fishcu] |

---

## 3. Minimum "film look" with stock settings only

Per COLOR profile (×3, plus the 4 custom banks), with no new code:
- **Saturation**, 12 sectors (931–966);
- **Highlights / Shadows / Midtones**, −7..+7 (967–975);
- **Contrast**, ±2;
- **Sharpness**, ±2;
- **Shading** (creative vignette, ±5).

With fishcu's HSL already installed: **Hue and Luminance, 12 sectors**.

Set globally and remembered by the user: Noise Filter (Off/Low/Std/High), lens Shading Comp. Off, and WB with its per-preset A-B/G-M shift (±7).

That covers the core of caduceus's recipes (per-family saturation, hue and lightness, contrast and tone; caduceus film sims use no grain, glow or art [pub]). It lacks the per-look WB shift, Blacks/Whites, Sharp Off, per-look NR and VigFix, grain, split toning and glow.

## 4. Extras that need new hooks (cheapest first)

1. **Per-look NR, VigFix, Sharp (incl. near-off):** one shared getter-override stub on `0x600750ee` call sites `0x60253657`, `0x60253540`, the five `0x8c21` sites, and the RAW-edit twins. ~100 B plus 7-B site patches [static].
2. **Per-look WB A-B/G-M:** about 9 sites, ~100 B [static].
3. **Blacks / Whites / highlight roll-off:** tone hook `0x604f85ea`, ~0.5 KB [static].
4. **Split toning:** selector hook `0x604f60d2`, ~150 B plus 1.5 KB buffers per context [static+emu].
5. **Soft Focus / Art Effects on COLOR:** `0xf5d1` getter at `0x60253b16` (+ RAW edit); weight/Clarity site still unknown [static].
6. **Colour grain:** route (a1), with ~4 overrides and +96 MiB of buffers per shot; or route (a2), the Grainy Film texture with combiner 1. Both are emulator-level only and need camera tests [static+emu].

All of them need per-capture transport of the look values (reuse or extend the H/L transport: the job has 16384-byte class headroom beyond the 14944-byte extended job [pub fishcu]). They also need code space. The PEN-F has no card-loaded code block like OM-3's GUIDES.BIN `xblock`, and HSL already uses the section-5 padding [pub/project memory], so space is the practical limit [spec].

## 5. Open questions (camera or emulator)

- (a1) Does the late `0xf005` combiner 33 pass grey a key-11 image? Does the mask pass need its 0x03a4 format and forced mono to work with a key-11 job? Is the full MONO work list memory-safe with RAW+JPEG and bursts?
- (a2) The combiner-1 config words (strength); the texture resource and its load gate at `0x604c66b9..0x604c6719`; whether the texture blend touches chroma.
- The Soft Focus weight site on the PEN-F; the live-view job-flag gate for Art Effects.
- Whether the O+0xc24 per-channel buffers are free when (61,sp) = 0.
- That ART key 0x..68 = Grainy Film: inferred from its I/II variants, the texture secondary input and the mono tint plus contrast curve in its 0x0101 pass [spec]. 0x..6b = Cross Process matches OM-3 [pub] and its three-curve result [emu].

## Scripts and outputs (scratchpad/agentB)

- `find_sid.py`, `sidtab.py`, `desc.py`: id-to-key table and descriptor value lists [static].
- `scripts/devcfg.py`: dev config for key 11/12 at stages 0/0x901/0x902 (tint word) [emu].
- `scripts/maskcfg.py`: mask tone, combiner and grain gain for key 11/12 [emu].
- `scripts/gfcfg.py`: Grainy Film and Cross Process config: combiner 1 at stage 0x100, the 0x0101 pass with mono tint and GF tone [emu].
- `scripts/artjobs.py`: art work lists (Grainy Film entries; Cross Process and Soft Focus = single COLOR entry with no effect flags) [emu].
- `scripts/gamma.py`: RGB gamma pointers for COLOR vs Cross Process [emu].
- `jobs_matrix/audit.json`: fishcu's `penf_creative_jobs_probe.py --matrix` (34 cases, 77 requests) [emu].
