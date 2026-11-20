# PEN-F 3101: platform pieces for a caduceus-om3-style firmware

Research notes, 2026-11-11. Read-only. Labels: **[static]** code/data reading of the
decoded main (base 0x60021020); **[emu]** native run in fishcu's MN103 harness;
**[pub]** caduceus-om3 docs (OM-3), not re-checked on PEN-F; **[fishcu]** a claim in
fishcu's oly_fw_analysis docs (his physical tests, not ours); **[cam]** a camera result
recorded in this project's docs.

Scratch scripts used (all in this folder): `space.py`, `holes.py` (build the current
image in memory through `build_hsl_combo.build()` with `build_hsl8f_afl_ovl.EDITS`;
package sha ed8b767f, matches the installed build), `gaprefs.py` (reference scan),
`extload.py` (native loader check).

---

## A. Code space

### A1. Section table and loader [static]

| | PEN-F 3101 | OM-3 [pub] |
|---|---|---|
| Descriptor table | 0x60026d7c, 8 x 12 B {dest, flash src, dest} (header "STARTS" at 0x60026d70) | 0x60029b28, 10 entries |
| Loader | 0x600421e1 (CALLS entry; reads (0xa1c583fc) = selector) | 0x60045ed5 |
| End selector | 0x600420c1: `cmp n,d0` chain, one `mov imm32,d0` per section | 0x60045e6c |
| Length | end - dest, read by flash wrapper 0x600720e1 (flags 0x101) into the uncached alias | same shape |
| Loaded mask | byte 0xa1c58404, bit (id-1); waiter 0x60042123 | 0xa32de590 |
| Request / waiter | 0x60042063 (request), 0x60042123 (wait + constructors 0x6006da8c for s1..5, s6 via the loader) | |
| Who loads | USTART tasks, unconditionally, in order 1..8: calls at 0x60041db6 (1), 0x601a70ed (2), 0x601a72f0 (3), 0x601a7efd (4), 0x601a7f27 (5), 0x601a7fac/bc/cc (6/7/8) | |

Flash source = 0x403a0020 + (dest - 0x60021020): every section is the file at its own
address (the decoded main is a flat image).

| Sec | Loaded range (end excl.) | End word (imm32 addr) | Next thing in file after the end |
|---|---|---|---|
| 1 | 0x60142800..0x601cb000 | 0x600420e5 | FF 0x601cb000..0x601ea800, then `.data` initializer 0x601ea800..0x6020b220 (copied to RAM 0x615fc540) and more data. Leave alone. |
| 2 | 0x6022a800..0x60428000 | 0x600420ed | FF 43008 B to s3 |
| 3 | 0x60432800..0x6069b800 | 0x600420f5 | FF 102400 B to s4 |
| 4 | 0x606b4800..0x60a50000 | 0x600420fd | FF 155648 B to s5 |
| 5 | 0x60a76000..0x60fdc800 | **0x60042105** | **FF 210944 B (206 KiB) to s6 0x61010000** |
| 6 | 0x61010000..0x610f2000 | 0x6004210d | FF 57344 B to the s7 region |
| 7 | 0x61100000 (length 0; loaded by CPU2 path) | 0x60042115 | FF 16 KiB 0x61100000..0x61104000 |
| 8 | 0x61104000..0x6115b800 | 0x6004211d | FF 8704 B, then data 0x6115da00..0x6115e9e7 (like OM-3's s10 data). Leave alone. |

Before s1: 0x60021020..0x60142800 is the boot part (its FF tails, e.g.
0x601305ad..0x60142800, are NOT shown to be loaded; same trap as OM-3's ext11 mistake).
Every end value occurs exactly once as an immediate (0x60a50000 has one more raw match at
0x60ddef8a, code bytes) [static].

### A2. What the current build uses, and what is left

All 8f/AF-limiter/overlay data and helpers are inside loaded ranges [static], and they are
camera-tested [cam: HANDOVER/BUILD_RECORD]. "HSL-free gaps in sections 2/3/4" means the
loaded FF tails (s2 ends 0x60428000, s3 0x6069b800, s4 0x60a50000), not inter-section gaps.
The only edit outside a section is 0x60207312 (AF limiter's `.data` initializer entry),
which is copied by startup, not executed [static][cam].

Use of each loaded FF tail (current build `hsl-8f-afl-ovl`, 44 edits / 662 B on top of HSL):

| Sec | Stock FF tail | HSL uses | Ours | Free now (holes >= 4 B) |
|---|---|---|---|---|
| 1 | 0x601caa04..0x601cb000 (1532) | 0x601caa50..0x601cafb6 | none | 0x601caa04..a50 (76, fishcu prefix margin), 0x601cafb6..b000 (74), plus 7/5/15 B holes inside HSL = **177** |
| 2 | 0x60427c30..0x60428000 (976) | 0x60427c70..0x60427fa8 | 0x60427e78..eb8 (Frame arrays), 0x60427fac..ffd (AFL labels) | 0x60427c30..c70 (64 prefix margin), 0x60427eb8..ed0 (24), 0x60427fa8..fac (4), 0x60427ffd..8000 (3) = **95** |
| 3 | 0x6069b26c..0x6069b800 (1428) | 0x6069b2b0..0x6069b7b9 | H4/H5 0x6069b270..b299, array B 0x6069b7bc..7ec | 4 + 23 + 17 + 12 + 20 = **76** |
| 4 | 0x60a4fe6c..0x60a50000 (404) | 0x60a4feb0..0x60a4ffb3 | H2 0x60a4fe70..ea6, H1/H3 0x60a4ffb4..fff7 | 4 + 10 + 9 = **23** |
| 5 | 0x60fdc29c..0x60fdc800 (1380) | 0x60fdc2e0..0x60fdc7a1 | H6 0x60fdc7a4..7bb, H7 0x60fdc7c0..7f3 | 0x60fdc29c..2e0 (68 prefix margin), 8, 5, 13 = **94** |
| 6 | 0x610f1e54..0x610f2000 | none | none | **428** (fishcu "proposed" 0x610f1ea0..0x610f1fc0 = 288 with margins) |
| 8 | 0x6115b014..0x6115b800 | none | none | **2028** (fishcu proposed 0x6115b060..0x6115b7c0 = 1888) |

Total about 2.9 KiB, of which 2.4 KiB is in sections 6 and 8 (untouched; fishcu's audit
lists them as candidates, `proven_unused: false`; no camera code has run there). The
prefix margins (64-76 B right after stock data) were kept free by fishcu on purpose. Small
holes inside HSL may be alignment padding of HSL routines. Sections 1-5 are effectively full.

### A3. Section extension: plausible, best target is section 5 [static][emu]

- Same mechanism as OM-3's camera-proven s6 extension [pub]: one immediate per section,
  the only reference. PEN-F s5's end word is the imm32 at **0x60042105** (instruction
  `mov 0x60fdc800,d0` at 0x60042103).
- The gap 0x60fdc800..0x61010000 (206 KiB) is all FF, inside the main component (the
  decoded main runs to 0x61480fe0; the component fills its 163 x 128 KiB flash allocation
  and the updater rewrites the whole component [fishcu RECOVERY.md]), so no container
  growth is needed. Flash for the extension = file bytes at the same offset.
- No immediate or `mov` reference into the gap in either alias except the end word; the
  aligned-word hits are code-byte noise (sampled: e.g. 0x610004c8 = bytes `c8 04 00 61`
  inside instructions) [static]. Dynamic use of that RAM (a computed heap, DMA) cannot be
  excluded statically; OM-3's GX probes found its gaps untouched [pub].
- **Native check [emu]** (`extload.py`): with the end word set to 0x60fdd800 (+4 KiB) or
  0x60fec800 (+64 KiB), the stock loader 0x600421e1 copies the marker in the extension
  exactly and returns normally; with the stock word the extension stays poisoned. Flash
  storage is modeled, so this shows the loader logic only.
- Loader side effects [static]: while loading, 0x6007f571 programs a bus-guard unit at
  0x99700000 over "next section dest .. s8 end" (end from 0x600420c1(8)); after s8 it
  calls 0x6007f498, which clears that and installs fixed low-address guard regions (tables
  0x6012aca0/0x6012acc0: 0..0x7fff, 0xa000..0x1fffffff, ...), none covering 0x60fdc800.. .
  So an s5 extension is not affected. Extending s8 would also move that guard's end and
  run into data/BSS (0x6115da00, `.data` copy at 0x61170fe0): avoid s8. Avoid s1 (data
  initializers in its gap) and s7 (CPU2 path, unknown owner of 0x61100000).
- Second choices: s4 end 0x600420fd (152 KiB gap), s3 0x600420f5 (100 KiB).

**Probe build sketch (PX1, mirrors caduceus GX1; not built):**
1. Base: `build_hsl8f_afl_ovl.EDITS`. Add the end word 0x60042105: 0x60fdc800 -> 0x60fdd800
   (PX2: 0x60fec800).
2. 0x60fdc800..: magic 'PXT1', a small probe routine, then an N-word pattern.
3. Report without file I/O: relocate H6 (EXIF 0x101c frame-count helper, called from
   0x60254850 only with Multiple Exposure on) into the s5 prefix margin 0x60fdc29c..2e0 as
   a guarded version: `mov (0x60fdc800),d0; cmp 'PXT1'; bne stock_h6; call probe`. The
   probe sums the pattern and writes a code (e.g. 0x51 = loaded+intact, 0x52 = loaded+bad)
   as the second 0x101c value; stock behaviour (frame count) if the magic is absent. Owner
   test: one 2f shot, then a video and a few shots, another 2f shot; read 0x101c with
   exiftool. A file report (GAPTEST-style) can follow once file I/O is wired (part B).
4. Build checks: update the loader check (BH.loader uses fishcu's audit end 0x60fdc800)
   to the new end, as `extload.py` does; run the usual preflight.
5. Only after the camera shows the code ran: put new code from 0x60fdc800 on.

---

## B. File I/O, half-press hook, gate, RAM word

### B1. stdio-style file API [static]

Found through the "file" debug shell (s8: `memdump`/`memload`/`sctest` handlers
0x6111ea0d / 0x6111ec9a / 0x6111eedb) and the olis "RESERVE file" code (0x605173b9..).
The wrapper block has exactly the OM-3 shape: fopen and fclose 9 bytes apart
(`clr d0; call core; ret`), then fwrite, fflush(?), fread, ftell, fseek in the same order.

| Function | PEN-F | Args (regs) | OM-3 [pub] |
|---|---|---|---|
| fopen | **0x60599595** (core 0x6059a415 with option d0) | a0 path, a1 mode -> a0 fp (0 = fail); 51 callers; modes seen "r","w","a","rb","wb","rd","wd" | 0x608d4d22 |
| fclose | **0x6059959e** | a0 fp | 0x608d4d2b |
| fwrite | **0x60599615** | a0 buf, d0 size, d1 n, a1 fp -> count | 0x608d4da9 |
| (fflush?) | 0x6059969e | a0 fp; 3 callers | |
| fread | **0x60599715** | a0 buf, d0 size, d1 n, a1 fp -> count; 33 callers | 0x608d4eb7 |
| ftell | **0x6059979e** | a0 fp -> (308,fp) position | 0x608d4f47 |
| fseek | **0x60599804** | a0 fp, d0 off, d1 whence: **2 SET, 0 CUR, 1 END** (core 0x6059efe5, size at fp+268) | 0x608d4fb1, same whence map |
| mkdir(?) | 0x605999d1 | a0 path, d0; used by 0x605173a6 when exists-check 0x6059a31f fails | |
| exists/stat(?) | 0x6059a31f | a0 path -> 0 if absent | |
| two-arg op (rename?) | 0x60599874 | a0, a1; 3 callers in s8 shell; unverified | |
| request-block ops | 0x60590d07 | 128 B block, op at +4: 1 stat, 2 rm, 3 rmdir, 5 mkdir (shell rm/rmdir/mkdir/chmod/cat) | |
| malloc | **0x60023459** | d0 size -> a0; pools <=128 / <=2048 / <=16384 B, larger -> error, 0 | 0x60024068 (<=192/<=2112/<=16448) |
| free | **0x60023498** | a0; pools 0xa1221fc0..0xa122a540, 0xa15f1800..0xa15fc540, 0xa142c540..0xa14d9000 (uncached aliases) | 0x6002409a |

Drive letter is "C:" (strings "C:\DCIM\100OLYMP\..." 0x604009ce) [static]. Paths like
`C:\PENFMOD\EDITS.BIN` should work; not tested.

Task safety [static]: every wrapper first calls 0x6059c8db: (0x8050) != 0 -> mode 2;
else current task id (getter **0x60031be2**, writes u16 at (a0)) compared with the FS
task id at (0x60040cf2): same task -> direct core call, other task -> the request is
copied into a malloc'd block and sent with 0x6006d323 (message 0x1000x) to the FS task,
waiting for the reply. So, unlike OM-3's "HLS task only" gate, any ordinary task can call
the API (it blocks while the card works). A code block loaded into heap is capped at
16384 B like GUIDES.BIN, and lives in the uncached alias (OM-3 found uncached code slow
[pub]).

### B2. Half-press hook candidate [static, not emulated]

- `press1stReleaseSubAppStateShootingStill` = **0x60baffba** (CALLS entry; plain 0x60baffbf),
  a virtual method: vtable words at **0x60db3810** and **0x60dbd384**. It calls
  `press1stRelease` 0x60bab501 (CALLS 0x60bab4fc; vtable words 0x60dbbf44, 0x60dbc6c4) for
  states 23045/23047.
- Hooking = replace one vtable word with a wrapper that runs our code then jumps to
  0x60baffba (no instruction patch). Which task runs it is open; if it is the application
  task that receives event 0x041b0011 (B4/C), do not post that event from it (deadlock);
  call the setters directly instead.
- Event names exist (`EV_PRESS_1ST_RELEASE` 0x60959252, `API_1ST_RELEASE`), for a
  lower-level hook if needed.

### B3. Gate pieces [static]

- All sections loaded: byte (0xa1c58404) == 0xff (HSL's Wi-Fi gate tests `& 4`).
- Settings recall not in progress: byte (0x6189a4b0) == 0 (HSL `wifi_recipe_allowed`,
  which also requires setting 41 == 0).
- Task id: 0x60031be2; FS task id (0x60040cf2).
- Media-ready word: **not found**. Candidate: per-device 92-byte records at 0xa1c77a64
  (via 0x6058a5c5(dev); dev = (0x61600784); +28 drive, +76 status bits). fopen returning 0
  may suffice as a soft gate; needs an emulator check with no card.

### B4. Spare RAM word: none qualified

- No stock store targets any loaded section (scan of all absolute `mov reg,(addr)`)
  [static], and no post-boot guard region covers 0x60xxxxxx, so a data word placed in our
  own cave or the s5 extension is RAM that is re-initialised from flash every boot (a free
  "boot-cleared" word). Writability is not demonstrated: add it to the PX probe (write,
  read back, report).
- An OM-3-style unreferenced singleton field was not searched for.
- For a persistent word: hidden setting 598 (C-AF Lock) is never read by AF code
  [cam/HANDOVER: hidden, unread], so it could hold e.g. a "current look" index.

---

## C. Settings storage

- **Run-time per-profile swap exists already in HSL's Wi-Fi recipe path** (fishcu
  `src/wifi/wifi.s`): marked writes go through the pending triple (0xa1c8a8b4 id,
  0xa1c8a8b8 0, 0xa1c8a8bc value 0x485Axxxx), event **0x041b0011** posted by 0x60aa4e7b,
  application receiver 0x608061b8 -> validated **stock_public_set 0x602b9f33** (d0 id,
  d1 value; verify with setting_get 0x602f024a) for scalars, and **hl_active_set
  0x60427cb4 + hl_publish 0x60427d60 + hl_refresh_profile 0x60427e09** for H/L cells
  [static]. fishcu reports physical tests: readback, capture, persistence after reboot,
  restoring a previous recipe [fishcu WIFI.md]. The validator allows S/H/L for 931-966,
  tones 967-975, contrast 916-918 (40 values); sharpness 913-915 and shading 1111-1113
  are outside it but stock_public_set takes any id.
- The editor's GUI path (607363b3 -> 6075fbed -> 602b9dac -> 602badc5 -> 602c50be) waits
  on GUI-worker replies and checks capture/busy [fishcu EDITOR.md]; better not called from
  a hook. A look loader should either post 0x041b0011 per value (from a non-application
  task; shares the pending triple with the HTTP worker, so skip when Wi-Fi is active) or,
  in the application task, call 0x602b9f33 / hl_active_set directly, as the receiver does.
- Per look: 18 COLOR ids per profile (916/913, 967-969/970-972/973-975, 1111-1113,
  931-942/943-954/955-966) plus 12 H/L cells (part 1 of 931-966) [CREATIVE_DIAL_MAP].
- **Spare persistent storage without a card:** only by repurposing. ART/CRT own about 52
  stored ids in arrays nothing else shares (keys 44c1, 44d1, dd61, dd71, f5e1, f609/
  f619/f629/9379; ART elements are 1 byte) [CREATIVE_DIAL_MAP]: room for about one extra
  look of 28-30 values, at the cost of ART/CRT and every path that writes them; whether
  those ids are saved in C1-C4 banks is open. Hidden setting 598 gives one word. A card
  file (EDITS.BIN-style) remains the practical store for several films.

## Open items

1. Camera probe PX1 (+4 KiB) then PX2 (+64 KiB) for s5; include a write/read-back of a
   data word in the extension.
2. Emulate fopen/fread/fclose through the FS task path (no card and card present) and
   find the media-ready state.
3. Find the task that runs 0x60baffba, then emulate a vtable-hook build.
4. Confirm 0x60599874 (rename?) and request op codes for rename; otherwise use an A/B
   pair of card files with magic/len/CRC instead of .NEW -> .BAK -> .BIN.
