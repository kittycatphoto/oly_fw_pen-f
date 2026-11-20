# Films v1 boot loop and the startup-safety gate (2026-11-11)

## What happened [cam]

The owner installed films v1 (package `3a71c846…9207`). The camera then switched itself on and off nonstop. It
recovered (the owner reports "Recovered already"). The fallback on the card was `hsl-8f-afl-ovl`
(`ed8b767f…b0f2f5`), flashed by holding OK at power-on; the owner has yet to confirm the method and the
current firmware. **The hold-OK SD update still worked.** So the loop happens after the update-mode
selection, in normal startup.

## Most likely cause: v1 code used before its section is loaded [static]

The startup order is in USTART4 (`0x601a7ed1`):
1. Load sections 4 and 5 (`0x601a7efd`, `0x601a7f27`), each followed by the waiter `0x60042123`, which runs the
   section's constructors.
2. Run section-4 start code (`0x606b4800`, `0x606b4892`), install the application callbacks, and cross a
   progress barrier (`0x600697ff`).
3. **Only then** load sections 6, 7 and 8 (`0x601a7faa..0x601a7fd3`).

Other startup tasks (USTART1 / USTART3) keep running in the meantime.

Films v1 put its code in the section-6 and section-8 tails, and pointed **always-used shared code** at it:

| Early site (section) | Points to | What uses it |
| --- | --- | --- |
| facade vtable `0x609a4660` / `4668` / `4684` (s4) | `fl_set` / `fl_get` / `fl_sel` (s8) | every setting read or write through OlyApiSettingController: 2,431 call sites, all in sections 4 and 5 |
| label lookup entry `0x60c8972a` (s5) | `fl_lk` (s8) | 243 GUI callers, all in section 5 |
| list record pointer `0x60c7f7f4` (s5) | film records (s8) | the Picture Mode list builder |
| 16 WB fine-tune getter calls (s3, s4, s5) | `wb_get` (s6) | capture set-up, live view, RAW edit |

Any facade or label use between the section-5 load and the section-8 load jumps into RAM that isn't loaded
yet. That gives a crash and a restart, every boot. That fits a boot loop, and it fits recovery still working:
the SD updater path doesn't go through the GUI facade.

**Evidence level:** static only.
- The load order is read from USTART4.
- The callers are counted by section. Every facade and label caller is in sections 4 and 5, which run before
  section 8 is loaded.
- Running the section 4 and 5 constructors natively stopped early on unmodelled RAM and peripherals
  (emulator: inconclusive). It neither confirms nor clears a facade call during construction.
- The concurrent tasks were not emulated.

**Precedent:** caduceus-om3 bootlooped once calling section-8 code from section-2 stage code [pub-cam].

**Why earlier builds were fine:**
- HSL, Live ND and the AF Limiter keep all their code in sections 1–5.
- The alignment probes ran code in section 6, but only from a capture-only trampoline in section 3 that first
  checks the "section 6 loaded" bit (`0xa1c58404` & `0x20`).

## Other candidates, ranked

1. **Code reached before its section is loaded** (above). High; static evidence.
2. **An integrity check over sections 6–8.** Low. None is known: the loader copies and sets a bit, and section-6
   edits have booted before [cam, alignment probes]. Section 8 had never been changed before, so a check
   specific to section 8 can't be fully excluded [static gap].
3. **The section-6-to-8 load-time bus guard.** Low. It covers "next section destination .. section 8 end" only
   while those sections load, and is replaced afterwards [static]. v1 writes nothing there at load time.
4. **Setting 597's widened list.** Low. The stored value is 0 until a film is picked, 0 is in both lists, and its
   only readers test `== 1` [static]. The rules engine allowed 0..20 [emu].
5. **The COLOR 3 posts.** Very low. They run only when a film is picked, never at power-on.

## The startup-safety gate (`probes/startup_gate.py`, private build tree)

**Rule:** any new code or data outside the loaded ranges of sections 1–5 must not be reachable from sections
1–5 (or from boot code and the `.data` initializer image). That means no call, jmp, calls or 32-bit word
pointing into it. The only exception is a waiver with a written reason. A waiver needs a guard like the
alignment probe's: check the section's loaded bit before jumping, from a path that only runs after startup.
New bytes outside every loaded section also fail.

**Calibration** [static]:

| Build | Result |
| --- | --- |
| `hsl-8f-afl-ovl` (camera-proven) | **PASS** |
| alignment probe 4 (camera-proven) | 1 early reference: the s3 trampoline → s6, guarded by the loaded bit and reached only from capture. Waivable |
| **films v1** | **FAIL**: 21 early references (16 WB calls, 3 vtable words, the label jump, the record pointer) |

**From now on:**
- Every build script runs the gate before its preflight and refuses to write a package on FAIL.
- The build record lists the gate report.
- The emulator constructor run is extended, as fixtures allow, to watch for execution of patched ranges.

## Fix for v1: v1-r2 (built 2026-11-11)

**v1-r2:** move all of v1's code and data into section 5, in the reclaimed `osd` debug-shell handler region
(`0x60a79cdc..0x60a7b434`, 5,976 B, `07_RECLAIM.md`). Stub the handler entry with `clr d0; rets`. Nothing
then lives in sections 6–8, and the gate must pass with no waivers.

**Still needed before a camera test:**
1. Confirm that no section-5 constructor runs the `osd` range. This is the gate's emulator half, as far as it
   reaches.
2. Re-run the v1 checks and the preflight.

**Result:**
- every new byte is in the `osd` region;
- startup gate: clean PASS;
- the `osd` region is reached only from the shell tables, which now hit the stub (4 raw-scanner hits were
  checked as bytes inside other instructions);
- the emulator suite and preflight pass, package `a7bb89bd…f22b`;
- recovery from the v1 loop is confirmed (hold-OK reflash of `hsl-8f-afl-ovl`).

## v1-r2 result and r3

- **v1-r2 on the camera:** startup fine. A freeze when the cursor moved onto a film.
- **Cause (static):** a cross-task wait (`stock_app_event` from the GUI task). This is not a startup problem.
- **r3:** removes it, as above.
- **Lesson:** any new code that runs from GUI events must use only paths the GUI itself uses, and never block on
  another task's reply.
