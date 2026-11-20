# Caduceus-style firmware on the PEN-F: research notes (2026-11-11)

These four notes back [CADUCEUS_PENF_ROADMAP.md](../../CADUCEUS_PENF_ROADMAP.md). Each came from a separate
read-only research pass on PEN-F build 3101. They contain addresses and findings only: no firmware bytes,
listings or decoded images. The probe scripts the passes wrote were kept out of the repository.

| File | Question |
| --- | --- |
| [01_PICTURE_MODE_LIST.md](01_PICTURE_MODE_LIST.md) | Can films sit in the Picture Mode list after Color Profile 1–3, and what would it take? |
| [02_LOOK_PARAMETERS.md](02_LOOK_PARAMETERS.md) | Which parts of a look the PEN-F can change, and where each would hook in |
| [03_PLATFORM.md](03_PLATFORM.md) | Code space after the current build, the section-end extension, card file I/O, storage |
| [04_OM3_TO_PENF_MAP.md](04_OM3_TO_PENF_MAP.md) | PEN-F counterparts of caduceus-om3's OM-3 hook sites, found by code-shape matching |
| [05_RWB_EMULATOR.md](05_RWB_EMULATOR.md) | Per-film WB shift: the 16 getter sites, the stub and its emulator results (R-WB) |
| [06_TONE_SPLIT.md](06_TONE_SPLIT.md) | v1.1: Blacks / Whites and split-toning hooks, per-shot transport, sizes |
| [07_RECLAIM.md](07_RECLAIM.md) | Reclaimable stock code (debug-shell handlers) for more space without a loader change |
| [08_STARTUP_SAFETY.md](08_STARTUP_SAFETY.md) | Films v1 boot loop: likely cause, ranked candidates, and the startup-safety gate |

Evidence labels: **[static]** = read from code or data, **[emu]** = run in the native MN103 emulator,
**[pub]** = from caduceus-om3 or fishcu docs and not re-checked, **[spec]** = inference. Nothing in these
notes is camera-tested.

## Corrections made while merging the notes

- **Tone hook.** 02 gives the luminance-LUT builder call `0x604f85ea` (`call 0x604f7c76,…,28`); 04 gives
  `0x604f85ef` (`mov d3,a0; call 0x604f7d50,…,76`). Both are right about different things. caduceus-om3
  hooks the step *after* the LUT builder (`mov d3,a0; call tone_next`, 7 bytes) and remaps the LUT the
  builder has just written. The PEN-F counterpart of that site is **`0x604f85ef`**, and the LUT builder
  itself is `0x604f7c76` [static, checked against the stage list at `0x604f8543`].
- **Code space.** 01 quotes "about 1.2 KB left in the section-3 tail" from older build notes. 03 measured the
  current build (`hsl-8f-afl-ovl`): sections 1–5 have about 465 B left in small holes, the section-3 tail only
  76 B. The untouched loaded tails of sections 6 (428 B) and 8 (2,028 B) are the real free space today
  [static]. The roadmap uses 03's figures.
- **Getter anchor.** OM-3 `0x603f0111` and PEN-F `setting_get` `0x602f024a` belong to different getter
  families. The PEN-F counterpart of OM-3 `0x603f0111` is `0x602b9da3` (04) [static].
