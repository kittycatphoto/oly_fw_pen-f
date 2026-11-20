# PEN-F 3101: reclaimable stock code inside loaded sections

Scope: these are stock regions inside sections 1–8 that could be overwritten
without changing the section loader. Ranges are end-exclusive runtime
addresses, and file offset = address − 0x60021020.
Everything here is **[static]**. Nothing was emulated or tested on hardware.

## Method [static]

1. **Reference index.** A linear objdump sweep of the whole decoded main
   collected `call/calls/jmp/bra/bcc` targets, imm32/absolute operands
   (cached 0x6…, and uncached 0xa… folded to 0x6…), and aligned 4-byte data
   pointers. A second raw byte-scan index of unaligned pointers and
   call/jmp opcodes at every offset was used only as a conservative cross-check.
2. **Node graph.** A node runs from each referenced address to the next one.
   Nodes that fall through without a terminator are chained to the next node.
3. **Seeds.** The three copies of the 59-entry RTOS shell table:
   - `601c8424` is U_SHELL. Its dispatcher `601a6f6c` is only called from the
     shell task `601a700e` and the line helper `601a6fa7/601a6fc2`.
   - `601c7414` is the `usr` sub-dispatcher `601a4d1d`.
   - `60d8a3c4` is S_SHELL, used from `60b2b11b`. Its line executor is
     reached through the S_SHELL jump table `60d62af0`.

   The SDK table `6097fa84` was *not* seeded: unseeded, it does not close.
4. **Closure.** A node counts as debug-only if every decoded reference to it
   comes from a seed or another debug-only node. Two passes were run: a least
   fixpoint, and a greatest fixpoint over the forward-reachable set, which
   handles mutual recursion. The results were merged.
5. **Checks on each candidate:**
   - Raw-index references into the range from non-debug nodes were spot-
     disassembled. All the checked ones are mid-instruction or data byte
     coincidences.
   - Flash aliases `0x4…`/`0x8…` (offset 0x1fc81000) only produced noise,
     for example `60042070 movbu d0,(0xa1c58405)`.
   - The other decoded components (0x101/0x106/0x102) were scanned for words
     in these ranges. They had scattered hits, none at a function entry.
   - The updater roots `60b1cbb5`, `60b1d527` and `60b1d012` are not in the
     debug set, and none of the candidate regions is referenced by
     non-debug code.
   - None of the candidates overlaps our current edits or reserved space.
     I checked `build_hsl8f_afl_ovl.EDITS` (44 spans), the extra
     `penf_films_build.EDITS` spans (including the s6 tail `610f1ea0..610f1f14`
     and the s8 tail `6115b060..6115b6b9`), and fishcu HSL `patch.json`
     main_ranges and data_edits: 222 spans in total. Address literals in
     probes/*.py, *.s, *.ld and the HSL patch were also checked.

Calling note: the shell dispatcher calls handlers with `calls (a1)`
(`601a6f8a`) and uses d0 as the result. Stock handlers return 0. A 3-byte stub
`00 f0 fc` (`clr d0; rets`) at a handler entry keeps the entry valid. This was
verified by assembling and disassembling it with the project objdump.

## Ranked table

"Usable" assumes the entry-stub method below. The "with table edit" figure
assumes the three shell-table slots point at a stub instead, which costs
3 × 4-byte data edits, in s1 ×2 and s5 ×1.

| # | Region (stock) | Usable contiguous | Sec | What it is / how reached | Neutralise | Risk | Evidence |
|---|---|---|---|---|---|---|---|
| 1 | `60a79cd6..60a7b435` (5983 B) | `60a79cdc..60a7b434` = **5976 B** (5983 with table edit) | 5 | `osd` shell command: OSD draw tests (`dot/line/rect/bmp/font/fcopy/setvram…`, "OSD DBG osddraw_init()"). Only entry is the handler `60a79cd6`, from table words `601c74f8`, `601c8508` and `60d8a4a8`. All 40+ internal nodes are referenced only from inside the region. Its shared epilogue `60a7b3f0` and parser `60a7b3f7` are only referenced from inside too. `60a7b435` onward is shared with normal OSD code, so stop before it. | Write `00 f0 fc` at `60a79cd6`; overwrite `60a79cdc..60a7b434`. | Low | [static] closure over both fixpoints. The `60a7b2cd` split was checked: the raw source `605ade70` is mid-instruction and the function runs on to `60a7b3f0`. The region writes byte `61606908`, but only when the command runs. |
| 2 | `60acded0..60aced6c` (3740 B) | `60ace0ac..60aced6c` = **3264 B** (+ `60acded0..60ace0a7` 471 B), or 3740 B with table edit | 5 | `spc` shell command: iSDIO/FlashAir command console ("-- spc dbg help --", isdio_write_command…). Handler `60ace0a7` sits inside the region, from table words `601c7570`, `601c8580` and `60d8a520`. `60acded0` is only called from `60aced5f`, which is inside the region. | Stub `60ace0a7`, or point the three table slots at a stub at `60acded0`. | Low–med. The nearby `spc_ctrl` code (`60acc6b2..60acdabe`) also closes as debug-only but is excluded here. Leave everything below `60acded0` alone: real Eye-Fi/FlashAir helpers live at `60acde6a..60acdebc`. | [static] |
| 3 | `60b02b86..60b03737` (2993 B) | `60b02b8c..60b03737` = **2987 B** | 5 | `efct` shell command: display/effect test (`set/coord/tft/pal/ntsc/direction/…/usb`). The handler is the region start, from table words `601c7538`, `601c8548` and `60d8a4e8`. It ends cleanly at the `ret` at `60b03734`. `60b03737` is a separate function. | Write `00 f0 fc` at `60b02b86`. | Low | [static] |
| 4 | `602e03c7..602e0c72` (2219 B) | 2219 B | 2 | Internals of the `app`/`api` shell commands (`api_debug.c`, help/show/exec/hist/key/tap…). The handlers `app 602e0c72` and `api 602e0cc5` sit just after the region. | Stub both handlers (`602e0c72`, `602e0cc5`); overwrite `602e03c7..602e0c72`. | Low–med. The closure's raw end `602e0cdd` is mid-instruction, so the region beyond the handlers is not used. | [static] |
| 5 | `601667f2..601672c0` (~2766 B) | ~2766 B | 1 | Subcommands of the `lens` shell command (LENS_SETUP…, aperture/focus/askdata…). It is called only from handler `60165cc1` (its body `60165cc1..601660f8`, 1079 B, is also debug-only). | Stub `60165cc1`. | Medium. Lens communication is shared with normal use and lens firmup (`60179914` and other `firmup` paths). The raw end `601672cd` was mid-instruction; I trimmed it to `601672c0` and the true end is unverified. | [static] |
| 6 | `602ca9a3..602cb000` (1629 B) | 1626 B | 2 | `stbd` shell command: strobe charge and endurance tests ("CHG START!!", "stb cloop"). | Stub `602ca9a3`. | Low–med | [static] |
| 7 | `60a9a147..60a9a76f` (1576 B) | 1573 B | 5 | `pos` shell command: GPS/position time debug help text. | Stub `60a9a147`. | Low | [static] |
| 8 | `60517b83..60518177` (1524 B) | ~1.4 KB | 3 | `olis` shell command: OI.Share image-reserve debug. Handler `60517c7d` is inside. | Stub `60517c7d`, or use a table edit. | Low–med | [static] |
| 9 | `605af045..605af4da` (1173 B) | 1170 B | 3 | `sdet` shell command: scene-detect debug dump. | Stub `605af045`. | Low | [static] |

The closure also found smaller regions under 1 KB: `pwr` handler
`60075fe8..600763cd` (997 B, s0), and lens info dumps at `6016c3cc` (1076 B),
`60167c65` (1043 B) and `6016b942` (881 B). In s8 it found the mcon debug
cluster `61107fc4..6110976e` (5.7 KB in 5 pieces) and `61105b16..61110ac8`
pieces of 1.3–2.3 KB. s8 is not preferred for pipeline code.

## Checked and not recommended

- **The `file` shell in s8** (`6111d2bf`; memdump/memload/sctest at
  `6111ea0d/6111ec9a/6111eedb`). Its body `6111d2c4` is also `call`ed from
  C3D debug code at `60ac79e7`, `60ac7a55` and `60ac7ad0`. Two of those
  callers (`60ac79f1`, `60ac7a5f`) have referrers (`60ac7fca`, `60ac8878`)
  that the closure could not prove debug-only. It is probably debug-only but
  not closed, and it is in s8.
- **The SDK/olyapi table `6097fa84`** (shutdown/sleep/power_info…). It is
  reached from `606f42dd`/`606f5a96` and does not close without seeding.
  It is power-management adjacent. Avoid.
- **Unreferenced blocks** (nodes with no inbound references), for example
  `60375a78` (3.7 KB, mostly zeros), `605159d6` (3.6 KB) and `60636cdc`
  (1.4 KB). Almost all of them follow a non-terminated node, so they are
  table or function interiors reached through base+offset. They cannot be
  shown unused statically.
- **Hardware-absent features outside the shell** (HDR button, PDAF tuning,
  FlashAir runtime, PENPAL, GPS). Their runtime code is referenced from
  normal settings/UI paths and none closes as unreferenced. Only the shell
  front-ends (`spc`, `pos`) are safe.

## Limits

- Static references cannot exclude computed addresses, DMA, or another
  core reading the region.
- These regions are only debug-only for stock firmware. Running the
  command before the patch is installed is irrelevant, but nothing may be
  left registered: no callbacks are installed at boot from these regions.
- Before use, confirm in the emulator that the section 5 constructors and a
  boot to live view never execute the overwritten range, for example with an
  execute watch on `60a79cd9..60a7b435`.

Scripts are in `agentF/scripts`: `mkidx2.py` (decoded index), `g2.py`
(closure), `evaluate.py`/`nodes.py`/`entries.py` (vetting), and `used.py`
(current edit spans → `used_spans.json`). Candidate data is in
`agentF/candidates.json`.
