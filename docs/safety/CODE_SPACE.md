# Finding space for added code

An FF-filled run is a candidate, not proof of free executable space. Firmware
bytes are copied into RAM sections; a large gap in the file can lie outside a
section load or overlap a later initialized/writable region.

## Qualifying a candidate

A useful audit establishes:

1. The section descriptor, logical source, runtime destination and exact loaded
   end. Check cached/uncached aliases and load order.
2. Neighboring tables' real bounds and constructors' byte counts. Do not assume
   they stop because padding contains FF.
3. Literal/relative references, with instruction boundaries and embedded data
   distinguished from real calls. Absence of static references cannot exclude
   computed accesses or DMA.
4. Native loading, execution and reload with the candidate bytes changed. Keep
   lower storage/cache assumptions explicit.
5. Runtime ownership, entry guards, ABI/alignment, stack use and any new writable
   state. Code residency is separate from flash-package acceptance.

PEN-F section 3 loads `60432800..6069b800`. Its FF suffix beginning at
`6069b26c` is inside that load. Reviewed neighboring consumers and all eleven
section-3 initializers run without accessing the selected interior. Apparent
branch patterns nearby include encoded CMIO and embedded image data, not
necessarily instructions. This supports a bounded placement claim, not proof
against every later access.

## Runtime and update risks are different

An alternative is to extend a section's loaded end. cmdada's
[E-M10 I loader](../tooling/e-m10/PLUGINS.md) changes two descriptor bytes to load
a larger tail. Independent emulation confirms the additional copy under a
modeled flash reader. This avoids relying on a tiny existing loaded suffix,
but still requires checking destination ownership, aliases and later reloads.

Executable camera code can reside in RAM. A lower-level section reload can reset
extension state even though the stored firmware bytes never change. Using an
uncached alias consistently avoids one class of accidental alias mixing; it does
not prove physical DMA/cache coherence or make concurrent reload safe.

The main firmware also contains flash-writing services for settings and update
operations. There is no demonstrated universal hardware lock that prevents
ordinary faulty application code from reaching all writable storage. Recovery
claims must retain the [pre-main and activation limits](../boot/pen-f/RECOVERY.md).

Tools: [PEN-F layout probe](../../tools/penf_section3_layout_probe.py),
[load probe](../../tools/penf_code_space_load_probe.py).
