# PEN-F 3101: per-film Blacks/Whites and split toning (agent E, 2026-11-11)

Read-only research. Labels: **[static]** = read in `generated/livend/main.dis` or the decoded image,
**[emu]** = stock code run natively (`scripts/tonegamma.py`, agent-B-style synthetic fixture),
**[pub]** = caduceus-om3 / fishcu docs and source, not re-checked, **[spec]** = inference.
Byte counts come from assembling the sizing sketch `scripts/tone_split_sketch.s` with
`toolchains/mn103-patch-build` (`scripts/sizes.sh`). The sketch has not been run or reviewed, and no build exists.

**Offset convention.** Here **O = output = C+12 = allocation+0x20c** (fishcu's "color output"). Earlier
notes mixed the two bases. The "RGB pointers at O+0x1430/34/38" in 02_LOOK_PARAMETERS are **allocation**-relative,
which is **output+0x1224/0x1228/0x122c**. The tone pointer is output+0x1230 and the tone buffer is output+0x1234.

> **Update 2026-11-13 (films v1.1a):** the per-capture transport in section 3 is not needed. The development
> request carries each shot's 12 signed saturation bytes at **request+1076** (fishcu's native packer probes), so a
> development hook can recognise the film from the request itself, with the same sectors-1–4 test the films build
> uses on the settings. v1.1a uses this for Blacks / Whites with the builder wrapper of section 1 (site
> `0x604f85e8`); see the roadmap, "v1.1a". The same recognition will serve split toning (v1.1b).

---

## 1. Blacks / Whites

### Site and LUT [static, emu]
- Stage list `0x604f8543` (callers `0x604f88f6`, mode R+28>>8 == 1, and `0x604f8912`, mode 2) ← dev-config builder
  `0x604f2973` (request kind R+16 ∈ {0, 14}) ← `0x604aa6cc` in the per-request configurator `0x604aa68a`.
  There is a single caller chain, so every kind-0/14 development request runs it. fishcu's camera-proven HSL hook
  (`0x604f7506`, inside `604f747f` in the same list) shows that this covers capture JPEG, preview/recview,
  live view (compact) and RAW edit [static + pub].
- **Bypass:** when R+1071 ∈ {1,2,3} and R+12 ∈ {0xa200, 0xa600}, predicate `0x604f2a64` sends the list
  through a reduced branch (`0x604f7c66` = ROM curve, no HSL, no tone hook) [static]. Films have no effect
  there, and neither does HSL.
- Builder call `0x604f85ea`: `call 0x604f7c76,[d2,d3,a2,a3],28` (5 B). The 7-byte unit `0x604f85e8` is
  `mov d3,a0` + that call. The caduceus-equivalent "after" site `0x604f85ef` is `mov d3,a0; call 0x604f7d50,…,76`
  (7 B) [static].
- `0x604f7c76` (C = d3, R = C+4, O = C+12):
  - If R+960 ≠ 0, the pointer comes from the art curve object.
  - Else, if **C+56 & 0x2e8063e**, it runs `0x604f7c18` → selector `0x604f75e5`. It returns **a ROM curve pointer**
    or, if `0x604f7be4` supplies a contrast table, composes into the buffer. The result goes to **O+0x1230**
    (job/context buffer **O+0x1234**, 256 × u16).
  - Then, if `0x604bdd21(R+948)`, it copies into O+0x1234 and post-processes with `0x604be08d`.
  - **If the gate is clear, nothing is written**: the pointer and buffer keep the previous pass's contents [static].
- Emulator, COLOR key 11 [emu]:
  - Gate set: pointer = `0x605fdd38` (the ROM curve; the buffer is untouched).
  - Gate 0: pointer untouched (19 instructions).
  - Gate = 0x2 alone behaves like all-dirty.
  - The ROM tone curve and the ROM gamma curve `0x605fdf38` are both 10-bit 0..1023 and monotone, the same scale as the OM-3 LUT. caduceus `remap()` therefore transfers bit-exact.
- Init: the context initialiser zeroes the tone pointer O+0x1230 and the RGB pointers O+0x41c/0x420/0x1224..0x122c (`0x604b2d31..0x604b2d45`) [static].
- Upload: `0x604b58c4` (called from `0x604b49d7`/`0x604b49f9`) copies the tone LUT to the ISP window. On the
  path at `0x604b59bd` it copies whenever O+0x1230 ≠ 0, with no dirty bit [static, partial read]. So a CPU remap
  before upload reaches the hardware.

### The stale-LUT trap (new) [static + emu]
The caduceus `tone` approach (remap in place at the "after" site) leaves O+0x1230 = O+0x1234 holding *our*
remapped curve. On the next pass, C+56 is a diff of request fields, so the builder gate is often clear. Film
Blacks/Whites are not request fields. The buffer then keeps the **previous film's** remap, or stays remapped
after the film is cleared. On the PEN-F this hits live view and any still developed on the same context.

**Recommended:** wrap the builder at **`0x604f85e8`** (7 B → `call tone,[d2,d3,a2,a3],28`).
1. For key 11, OR bit 1 (0x2, inside the builder's mask) into C+56.
2. Call the stock builder (`mov d3,a0; call 0x604f7c76,…,28`, nested).
3. Restore C+56.
4. Copy the curve to O+0x1234 if it isn't there already, remap by Blacks/Whites, and point O+0x1230 at it.

The LUT is regenerated on every COLOR pass, so the result is exact, and no other stage sees the forced bit.

### Size
- `tone` (caduceus maths, offsets 3828→0x1230, 3832→0x1234, art R+1568→R+960, gate C+60&0x4134063e → C+56&0x2e8063e,
  plus the force/restore and the job reader call): **281 B**, measured.
- Per film: 1 B (Blacks/Whites signed nibbles −5..+5). Site: 7 B.

## 2. Split toning

### Correction: the selector is `0x604f5b17`, not `0x604f2a94` [static, emu]
- RGB gamma stage `0x604f6083` (stage-list call `0x604f8588`, 7 B with its `mov d3,a0`).
- **`0x604f609d`: `call 0x604f5b17,[d2,d3,a2,a3],28` (5 B).**
  - It writes the R/G/B curve pointers to (64/68/72,sp) and returns the (61,sp) flag.
  - It is the counterpart of OM-3 `0x605163f8`: R+1092 == 257 row, art override R+960, id hash `0x60626ff0`.
- `0x604f2a94` at `0x604f60d2` fills a 6-halfword descriptor at sp+96 from R+1044/R+996. The stage later copies it
  into the cache object +12. It is not the curve selector.
- **Packing copier** `0x604f5f7b` (and the two-bank `0x604f5ff1`) → inner `0x604f5f11`:
  - Packs entry i as `R | G<<10 | B<<20` (each `& 1023`) into a **256 × u32 table at O+0x424 (bank 1) or O+0x824 (bank 2)**.
  - Sets O+0x41c / O+0x420 to the active table (the other to 0).
  - Stores the three source pointers at **O+0x1224/0x1228/0x122c**.
  - When R = G = B pointers it takes a single-channel fast path [static].
- Emulator [emu]:
  - COLOR key 11 → src = `0x605fdf38` ×3, bank 2 (O+0x824), R = G = B, 0..1023, monotone.
  - Cross Process I `0x0101006b` → three curves `0x605fef38/0x605ff138/0x605ff338`, R ≠ G ≠ B.
  - **The copier ran even with C+56 = 0**, because R+924 = 0 means no cache object, so no skip test.
  - The skip path (`0x604f630f`, which clears C+100 bits 0–1) is only reachable with a cache object (R+924 → +5596) and equal pointers.
- Optional per-art buffers at O+0xc24/+0xe24/+0x1024 (3 × 512 B, written by `0x604fc3e8` when (61,sp) ≠ 0).
  Another stage uses O+0xe24 as scratch (`0x604f8c27`) [static]. **Do not use them.**

### Where the bend lives: in place, no extra buffer [spec]
Bend the packed table the copier has just written, at the copier join **`0x604f62dc`**:
- The site is 6 B: `cmp 0,d2; beq 0x604f631b; mov (64,sp),d0`. Branch targets `0x604f62b5`/`0x604f62cb` land on its first byte.
- Replace it with a 5-B `jmp` + `nop`. The stub saves d2/d3/a2/a3 and handles both banks (O+0x41c/0x420 ≠ 0).
- For each entry and channel, with v = 10 bits and s = 1023 − v:
  - ws = ((v·s>>10)·s)>>10
  - wh = ((v·v>>10)·s)>>10
  - v += (Ks_c·ws + Kh_c·wh)>>8, clamped to 0..1023
  - This is caduceus `model.py` rescaled to 10 bits.
- Ks/Kh come from a 12-colour × RGB s8 table × strength. Black and white stay fixed.
- The stub then sets **C+100 |= 3**, so the RGB upload (gated on C+100 bit 0/1 in `0x604b5946`/`0x604b597c`) happens
  even when the film changed but the request did not. It replays the 3 instructions and jumps to `0x604f62e2`.

The table is rewritten from the source curves every time the copier runs, so the bend is idempotent per pass.
It works on top of Cross Process too, unless you gate on key 11.

### Size
- `split`: **272 B**, measured. Colour table: 36 B. Per film: 2 B (shadow and highlight: colour nibble + signed strength nibble).
- Site: 6 B. Runtime ≈ 256 × 3 × ~30 instructions per pass (live view too) [spec].

## 3. Per-capture transport

### Recommended: a film byte beside fishcu's H/L [static, spec]
- **Acquire:** patch the entry of fishcu `hl_source_to_owner` (`0x6069b44c`; `mov a0,a3` 1 B + `call hl_owner_row` 5 B = 6 B → `jmp tr_src`).
  - This one point covers capture acquire `0x60253c7f`, compact acquire `0x605576ec` and RAW-edit acquire `0x60af2f56` (COLOR path).
  - `tr_src` computes film = (capture +18595 == 11 and +18625 == 3, or compact +381 == 3) ? `getter(0xe8c1,0) − 2` (valid 0..18) + 1 : 0.
  - It stores the result in our 45-byte `TN_ROWS[(row − hl_rows)/12]`.
  - Setting 597 = key **0xe8c1** idx 0 (table `0x603fa158`) [static].
- **To job:** patch the entry of `hl_owner_to_job` (`call hl_owner_row`, 5 B → `jmp tr_job`).
  - This covers capture_to_job `0x605205f9`, compact_to_job `0x6055a28a` and recording_to_job `0x605323f8` (the saved JPEG).
  - It writes `TN_ROWS[k]` (or 0) to **job+14944** (a2+24).
- **Job member:** extend the job 14944 → 14948 B, still in the 16384-B class. This takes two data edits on top of HSL's:
  `0x604c1c0f` imm 0x3a60 → 0x3a64 (alloc) and `0x604c1d1f` `85 24` → `85 28` (zeroing 14908 + 40) [static].
  The only other 14920/14908 users are stock field accesses (`0x604c2f9b`, `0x604c37c6`) [static].
- **Dev reader** `tn_film` (shared by both hooks; fishcu's own validation):
  - R+10 == 11, R+0 == `0x604c4011`.
  - R+4 matches one of the 16 records at R+1848 + 52i, and record+0 == R − 12228.
  - Then it reads job+14944 and indexes the film table.
- **RAW+JPEG / delayed processing:** both developments of a shot come from the same owner row, written once at
  the shutter. A later change to 597 does not reach them. Non-job requests and unknown owners give film 0.
- **Known gap:** the RAW neutral (non-COLOR) path writes fishcu's row directly and leaves our byte stale. That is
  harmless, because those jobs are not key 11.

### Is reading 597 in the pipeline safe?
- **At the acquire sites: yes, as safe as stock.**
  - All three sites sit among stock calls to the same key getter `0x600750ee`: `0x60253c75`/`0x60253c88`; `0x605576d7` (loop just before); `0x60af2ef4`/`0x60af2f7d` [static].
  - Call `0x600750ee(0xe8c1, 0, a0 = 0)` directly, not `setting_get`. `setting_get` `0x602f024a` = table lookup + the same getter. On CPU0 it also lazily writes a pointer cache (`0x602f03be`: `0xa1c58bb4 + 4·id`) [static].
  - The key getter is lock-free:
    - Hash lookup `0x600745e2` (an error call only for unknown keys).
    - Per-CPU address translation `0x60073628` through (0x8050).
    - A load [static].
- **Inside the dev hook: avoid it.** It is not a crash risk in the code: the getter takes no lock or OS call, and caduceus's camera-proven OM-3 `tone` calls the OM-3 key getter (63153) from the identical stage [pub]. It is a correctness risk:
  - The second RAW+JPEG development and RAW edit of an older file would use the *current* film.
  - Compact jobs may develop on CPU2.
- **caduceus v0.24's reboot** [pub]:
  - The trigger was the *setting-id* getter AGET `0x603f039d`, called inside the capture Art-Effect converter from **heap-block code** (`xb_cap`).
  - The key getter call in `xb_slot`, just before it, was already camera-proven.
  - Their fix removed the AGET call. Their own diagnosis is "likely" and was not bisected further.
  - Lessons (lk6): capture/AE hooks stay in flash-loaded code, which ours are, and a heap block is not.
- **Hardening for films v1** [spec]: `wb_get` calls `setting_get(111)`/`(597)` at capture/compact WB sites. The equivalent key-getter calls are `0x9481`/`0xe8c1`, idx 0.

### Cheaper but less correct alternative
Read `getter(0xe8c1)` (and check profile 3) inside `tn_film` instead of transporting.
- Saves ≈ 200 B (the reader shrinks to ≈ 50 B; no rows, no entry patches, no constructor edits).
- Live view and normal stills would be right.
- RAW+JPEG with a film change between the two developments, and RAW edit of old files, would be wrong.

## 4. Emulator vs camera

| Emulator can check (native MN103, synthetic C/R/O + fishcu fixtures) | Camera only |
|---|---|
| Tone builder gating and pointer (done: ROM pointer, gate clear = no write); the forced-bit wrapper regenerates the LUT; the remap equals caduceus `remap()` bit-exact on the ROM curve | Visual result, ISP behaviour, LUT upload timing |
| Gamma stage: copier always runs for synthetic key 11 (done); bent bank contents, monotonicity, both banks; Cross Process unaffected when gated | Whether real COLOR requests carry R+924 (cache object): if so, the skip path, and whether C+100 \|= 3 suffices |
| Uploader `0x604b58c4` with C+100 bits: table reaches the ISP window (fishcu `reenter(0x604b4933)` pattern) | Live-view frame-rate cost of the 768-step bend + 256-step remap |
| Transport: `tr_src`/`tr_job` with fishcu's ownership tests (40 + 5 owners, record 15, unknown owner, compact path); constructor zeroes job+14944 | Real scheduling: RAW+JPEG double development, delayed processing, CPU2 compact jobs |
| Key getter for 0xe8c1 on the boot checkpoint | Getter safety on the real capture path (static evidence only) |

## 5. Totals (measured sketch; ±15 %, not optimised)

| Item | Bytes |
|---|---|
| Shared transport: `tr_src` 118 + `tr_job` 45 + `tn_film` 79 | 242 code |
| `TN_ROWS` (writable loaded section) | 45 |
| Transport entry patches inside HSL code (6 + 5) + constructor edits (3 + 1, data) | 15 |
| `tone` + site | 281 + 7 |
| `split` + colour table + site | 272 + 36 + 6 |
| Per film (19) | B/W 1 B → 19; split 2 B → 38 |

- **(a) Blacks/Whites alone:** 281 + 242 + 45 + 19 = **≈ 587 B** new code/data + 22 B of site/data edits.
  Without transport: ≈ 350 B.
- **(b) Split toning alone:** 272 + 36 + 242 + 45 + 38 = **≈ 633 B** + 21 B of edits. Without transport: ≈ 400 B.
- **(c) Both:** 281 + 272 + 242 + 45 + 36 + 57 = **≈ 933 B** (952 B with 4-byte film records) + 28 B of edits.
  Without transport: ≈ 700 B.

**Space:** after films v1, the loaded tails left are s8 263 B and s6 172 B inside fishcu's margins (≈ 435 B),
or ≈ 715 B without the margins [films_v1_preflight.log, 03_PLATFORM].
- (a) and (b) each need the margins.
- (c) needs the section-5 extension (PX1 probe) or other relocation.
