# PEN-F 3101: Caduceus-style films v1.1 (r8 + Blacks/Whites + split toning). Older notes follow.
# r5: fl_lk gives the film name for ANY text table (value 56's entry has type 4),
# and COLOR 3's entry for picture tables.
# r4: no film-state setting. The active film is recognised from COLOR 3's own
# stored saturation (fl_ident: first 4 sectors, unique across the 19 films),
# which the camera keeps over power-off. Setting 597 is no longer used.
# Films listed after COLOR 3 in the SCP / Live Control Picture Mode list.
# Picking film j loads its looks onto COLOR 3 (overwrite approved by the
# owner) and switches to COLOR 3; the film's WB shift is added while a film
# is active on COLOR 3. (v1-r3 and earlier: film state in setting 597 [HDR]+[BKT]
# option, readers only test == 1): 0 none, j + 2 for film j.
#
# Symbols from the build (--defsym): FV (film value base), NFILMS, FL_RECS,
# FL_LAB, FL_VALS (21 B per film, nibbles), FL_TAIL (5 x u16 ids), WBTAB,
# and the link-time stock addresses below.

	.set	CURSOR_RET, 0x60c7f898		# builder: return of its cursor GetValue(910)
	.set	LABELS, 0x60f59a28		# item 0x1a label array (Color Profile 1-3)
	.set	ICONS1, 0x60f58fc0
	.set	ICONS2, 0x60f59680
	.set	AXIS, 0xa069b7b8		# HSL editor axis byte (0 S, 1 H, 2 L)
	.set	MAILBOX, 0xa1c8a8b4		# native pending triple (id, 0, marked value)
	.set	EV_SET, 0x041b0011		# app event that runs HSL's wifi_recipe_receive
	.set	KEY_AB, 0x84f9
	.set	KEY_GM, 0x9679

# ---------------------------------------------------------------- section 8
	.section .fl_code,"ax"

# Facade slot 9 selectable(a0 this, d0 id, d1 value) -> d0. Entered by CALLS.
	.global	fl_sel
fl_sel:
	cmp	910,d0
	bne	9f
	cmp	FV,d1
	bcs	9f
	cmp	FV + NFILMS,d1
	bcc	9f
	mov	1,d0
	rets
9:	jmp	STOCK_SEL

# Facade slot 2 get(a0 this, d0 id, a1 out) -> d0 0. Entered by CALLS.
# Only the list builder's cursor read sees the film value.
	.global	fl_get
fl_get:
	cmp	910,d0
	bne	9f
	mov	mdr,d1
	cmp	CURSOR_RET,d1
	bne	9f
	movm	[d2,d3,a2,a3],(sp)
	add	-12,sp
	mov	a0,a3
	mov	a1,a2
	call	fl_ident,[d2,d3,a2,a3],28
	cmp	0,d0
	blt	7f
	add	FV,d0
	mov	d0,(a2)
	clr	d0
	ret	[d2,d3,a2,a3],28
7:	mov	a3,a0
	mov	a2,a1
	mov	910,d0
	calls	STOCK_GET
	ret	[d2,d3,a2,a3],28
9:	jmp	STOCK_GET

# Facade slot 0 set(a0 this, d0 id, d1 mode, a1 value) -> d0. Entered by CALLS.
	.global	fl_set
fl_set:
	cmp	910,d0
	beq	1f
	jmp	STOCK_SET
1:	movm	[d2,d3,a2,a3],(sp)
	add	-20,sp
	mov	d1,(4,sp)			# original mode
	mov	a1,(8,sp)			# original value
	mov	a0,a3				# facade
	mov	a1,d2
	cmp	FV,d2
	bcs	50f
	sub	FV,d2
	cmp	NFILMS,d2
	bcc	60f
# load film d2: 41 values from FL_VALS + 21 * j, low nibble first.
# r3: every value goes through the stock facade setter from this (GUI) task.
# HSL's camera-proven hook inside it (0x6073659d) writes the H or L cell when
# its editor axis byte is 1 or 2, so the axis is set per value (S 0, H 1, L 2)
# and put back afterwards. No app events, no waits on another task.
	movbu	(AXIS),d0
	movbu	d0,(16,sp)
	clr	d0
	movbu	d0,(AXIS)
	mov	d2,d0
	mov	21,d1
	mul	d1,d0
	mov	FL_VALS,a2
	add	d0,a2
	clr	d3
2:	mov	d3,d0
	lsr	1,d0
	mov	a2,a0
	add	d0,a0
	movbu	(a0),d0
	btst	1,d3
	beq	3f
	lsr	4,d0
3:	asl	28,d0
	asr	28,d0				# signed nibble
	mov	d0,a1
	cmp	12,d3
	bcs	10f				# 0..11 saturation
	cmp	24,d3
	bcs	20f				# 12..23 hue
	cmp	36,d3
	bcs	30f				# 24..35 luminance
	mov	d3,d1				# 36..40: contrast, sharpness, tones H/M/S
	sub	36,d1
	asl	1,d1
	mov	FL_TAIL,a0
	add	d1,a0
	movhu	(a0),d0
	clr	d1
	bra	40f
10:	mov	d3,d0				# saturation: axis S
	add	955,d0
	clr	d1
	bra	40f
20:	mov	d3,d0				# hue: axis H (HSL's setter hook writes the H cell)
	add	955 - 12,d0
	mov	1,d1
	bra	40f
30:	mov	d3,d0				# luminance: axis L
	add	955 - 24,d0
	mov	2,d1
40:	movbu	d1,(AXIS)
	mov	a3,a0				# facade set(id, 0, value); HSL's hook at 0x6073659d handles H/L
	clr	d1
	calls	STOCK_SET
45:	inc	d3
	cmp	41,d3
	bcs	2b
	movbu	(16,sp),d0
	movbu	d0,(AXIS)
	mov	a3,a0				# switch to COLOR 3
	mov	910,d0
	clr	d1
	mov	56,a1
	calls	STOCK_SET
	ret	[d2,d3,a2,a3],36
50:						# COLOR k picked: nothing extra (the film is recognised from COLOR 3)
60:	mov	a3,a0				# stock with the original arguments
	mov	910,d0
	mov	(4,sp),d1
	mov	(8,sp),a1
	calls	STOCK_SET
	ret	[d2,d3,a2,a3],36

# fl_ident -> d0 = film j (0..NFILMS-1) when the picture mode is COLOR 3 and
# its saturation sectors 1-4 equal film j's, else -1. Entered by
# "call fl_ident,[d2,d3,a2,a3],28" (16 B of saved registers + 12 B locals; (0,sp) is
# the nested calls' return slot, locals at (4..8,sp)).
	.global	fl_ident
fl_ident:
# On the camera setting_get(111) reads 11 (the COLOR family code) with COLOR 3
# active, not 56 (r6 diagnostic, 2026-11-12). COLOR 3 is mode 56, or mode 11
# with profile setting 1086 == 3 (camera-confirmed with r7).
	mov	111,d0
	call	setting_get,[],4
	movbu	d0,(9,sp)			# mode low byte (local)
	mov	1086,d0
	call	setting_get,[],4
	movbu	d0,(10,sp)			# profile low byte (local)
	clr	d2
1:	mov	d2,d0
	add	955,d0
	call	setting_get,[],4
	mov	sp,a0
	add	d2,a0
	movbu	d0,(4,a0)
	inc	d2
	cmp	4,d2
	bcs	1b
	movbu	(9,sp),d0
	cmp	56,d0
	beq	4f
	cmp	11,d0
	bne	8f
	movbu	(10,sp),d0
	cmp	3,d0
	bne	8f
4:
	movbu	(4,sp),d0			# packed like FL_VALS: sector 1 | sector 2 << 4
	and	15,d0
	movbu	(5,sp),d1
	and	15,d1
	asl	4,d1
	or	d1,d0
	mov	d0,d2
	movbu	(6,sp),d0			# sector 3 | sector 4 << 4
	and	15,d0
	movbu	(7,sp),d1
	and	15,d1
	asl	4,d1
	or	d1,d0
	movbu	d0,(8,sp)
	clr	d3
	mov	FL_VALS,a2
2:	movbu	(a2),d0
	cmp	d2,d0
	bne	3f
	movbu	(1,a2),d0
	movbu	(8,sp),d1
	cmp	d1,d0
	bne	3f
	mov	d3,d0
	ret	[d2,d3,a2,a3],28
3:	add	21,a2
	inc	d3
	cmp	NFILMS,d3
	bcs	2b
8:	mov	-1,d0
	ret	[d2,d3,a2,a3],28

# Label lookup 0x60c8972a(a0 out-ish, d0 value, a1 array, d1 count), entered
# by "jmp fl_lk" in place of its first 5 bytes (mov a0,(4,sp); clr d2;
# clr d3; cmp d2,d1). d2/d3 are cleared right after, so they are free here.
	.global	fl_lk
fl_lk:
	cmp	FV,d0
	bcs	9f
	cmp	FV + NFILMS,d0
	bcc	9f				# only the film window FV..FV+NFILMS-1
	mov	a1,d2
	cmp	LABELS,d2
	bne	2f
	mov	d0,d3				# the picture-mode label table: film name record
	sub	FV,d3
	mov	d3,d2				# a1 = FL_LAB + 12 * j, d1 = 1
	add	d3,d3
	add	d2,d3
	asl2	d3
	mov	FL_LAB,a1
	add	d3,a1
	mov	1,d1
	bra	9f
2:	mov	a0,(4,sp)			# other table: find value 56's entry and its type
	mov	a1,a0
	mov	d1,d2
3:	cmp	0,d2
	beq	5f
	mov	(a0),d3
	cmp	56,d3
	beq	4f
	add	12,a0
	add	-1,d2
	bra	3b
4:	movhu	(4,a0),d3
	cmp	4,d3
	bne	5f
	mov	(4,sp),a0			# a text table: film name record
	mov	d0,d3
	sub	FV,d3
	mov	d3,d2
	add	d3,d3
	add	d2,d3
	asl2	d3
	mov	FL_LAB,a1
	add	d3,a1
	mov	1,d1
	bra	9f
5:	mov	(4,sp),a0			# a picture table (or no COLOR 3 entry): COLOR 3's entry
	mov	56,d0
9:	mov	a0,(4,sp)
	clr	d2
	clr	d3
	cmp	d2,d1
	jmp	LOOKUP_RESUME


# ---------------------------------------------------------------- section 6
# WB fine-tune getter wrapper (R-WB design). All 16 reads of the A-B / G-M
# keys call it as "call wb_get,[d2,d3],12" (d0 key, d1 index, a0 0).
	.section .wb_get,"ax"
	.global	wb_get
wb_get:
	mov	d0,d2
	call	GETTER,[d2,d3],12
	mov	d0,d3
	call	fl_ident,[d2,d3,a2,a3],28
	cmp	0,d0
	blt	9f
	mov	WBTAB,a0
	add	d0,a0
	movbu	(a0),d0
	cmp	KEY_AB,d2
	bne	1f
	asl	24,d0
	bra	2f
1:	cmp	KEY_GM,d2
	bne	9f
	asl	28,d0
2:	asr	28,d0
	exth	d3
	add	d0,d3
	cmp	7,d3
	ble	3f
	mov	7,d3
3:	cmp	-7,d3
	bge	9f
	mov	-7,d3
9:	mov	d3,d0
	ret	[d2,d3],12

# ---------------------------------------------------------------- v1.1a: per-film Blacks / Whites
# Replaces the 7 B at 0x604f85e8 ("mov d3,a0; call 0x604f7c76,[d2,d3,a2,a3],28") in the development stage
# list 0x604f8543 with "call tn_tone,[d2,d3,a2,a3],28": same register list, frame and return address.
# d3 = context C; C+4 = request R; C+12 = output O; O+0x1230 = active tone LUT pointer (256 x u16, 10-bit);
# O+0x1234 = the context's own 512-B LUT buffer; C+56 = the pass's dirty mask (builder gate & 0x2e8063e).
#
# For a COLOR request (key word R+8 == 0x000b0000, as 0x604f74d8 tests) with no art curve (R+960 == 0):
#  1. C+56 |= 2 around the stock builder, so it re-selects the stock curve every pass (no stale remap),
#     then C+56 is restored for the later stages.
#  2. The film comes from the request itself: R+1076 holds the shot's 12 signed saturation bytes (fishcu,
#     native), so sectors 1-4 identify film j exactly as fl_ident does from the settings. Live view, the
#     saved JPEG, RAW+JPEG second developments and RAW edit all carry their own values: no transport, no
#     settings reads in the pipeline.
#  3. Film with Blacks/Whites: copy the LUT into O+0x1234 if it is not there, point O+0x1230 at it, remap
#     with caduceus remapBW() (lo, cB, cW, K precomputed per film in FL_BW, 8 B each; K == 0 = none).
# Locals: (0,sp) nested-call return slot; (4,sp) saved C+56; (8,sp) running max.
	# TONE_BUILD = 0x604f7c76 comes from the link (--defsym), as GETTER does: an assembler .set gives a wrong pc-relative call
	.global	tn_tone
tn_tone:
	mov	d3,a2				# C
	mov	(4,a2),a1			# R
	mov	(8,a1),d0
	cmp	0x000b0000,d0
	bne	90f				# not COLOR: stock
	mov	(960,a1),d0
	cmp	0,d0
	bne	90f				# art curve: stock
	mov	(56,a2),d0
	mov	d0,(4,sp)
	or	2,d0
	mov	d0,(56,a2)
	mov	d3,a0
	call	TONE_BUILD,[d2,d3,a2,a3],28
	mov	d3,a2
	mov	(4,sp),d0
	mov	d0,(56,a2)			# dirty mask back for the later stages
	mov	(4,a2),a1
	add	1076,a1				# the shot's saturation, sectors 1-4
	movbu	(a1),d0
	and	15,d0
	movbu	(1,a1),d1
	and	15,d1
	asl	4,d1
	or	d1,d0
	mov	d0,d2				# sector 1 | sector 2 << 4
	movbu	(2,a1),d0
	and	15,d0
	movbu	(3,a1),d1
	and	15,d1
	asl	4,d1
	or	d1,d0				# sector 3 | sector 4 << 4
	clr	d3
	mov	FL_VALS,a0
1:	movbu	(a0),d1
	cmp	d2,d1
	bne	2f
	movbu	(1,a0),d1
	cmp	d0,d1
	beq	3f
2:	add	21,a0
	inc	d3
	cmp	NFILMS,d3
	bcs	1b
	bra	99f				# no film
3:	asl	3,d3				# FL_BW + 8 j: u16 lo, u8 cB, u8 cW, u32 K
	mov	FL_BW,a0
	add	d3,a0
	mov	(4,a0),d0
	cmp	0,d0
	beq	99f				# film without Blacks/Whites
	mov	(12,a2),a3			# O
	mov	(4656,a3),a1			# active LUT
	cmp	0,a1
	beq	99f
	mov	a3,d1
	add	4660,d1
	mov	d1,a2				# a2 = O+0x1234 (C no longer needed)
	cmp	a2,a1
	beq	5f
	clr	d1
4:	movhu	(d1,a1),d2
	movhu	d2,(d1,a2)
	add	2,d1
	cmp	512,d1
	bcs	4b
	mov	a2,(4656,a3)
5:	mov	a0,a3				# a3 = film's B/W record
	mov	a2,a1
	add	512,a1				# end
	clr	d0
	mov	d0,(8,sp)			# running max
6:	movhu	(a2),d0
	cmp	1023,d0
	bls	7f
	mov	1023,d0
7:	movbu	(2,a3),d1			# cB: y -= (cB * (((t*t)>>10)*t>>10)) >> 10, t = 1023 - y
	cmp	0,d1
	beq	8f
	mov	1023,d2
	sub	d0,d2
	mov	d2,d3
	mul	d2,d3
	lsr	10,d3
	mul	d2,d3
	lsr	10,d3
	mul	d1,d3
	lsr	10,d3
	sub	d3,d0
	bge	8f
	clr	d0
8:	movbu	(3,a3),d1			# cW: y += (cW * (((y*y)>>10)*y>>10)) >> 10
	cmp	0,d1
	beq	9f
	mov	d0,d3
	mul	d0,d3
	lsr	10,d3
	mul	d0,d3
	lsr	10,d3
	mul	d1,d3
	lsr	10,d3
	add	d3,d0
	cmp	1023,d0
	bls	9f
	mov	1023,d0
9:	mov	(4,a3),d1			# y = lo + ((y*K + 0xfffff) >> 20), unsigned 32-bit
	mulu	d1,d0
	add	0xfffff,d0
	lsr	20,d0
	movhu	(a3),d1
	add	d1,d0
	mov	(8,sp),d1			# monotone: y = max(y, prev)
	cmp	d1,d0
	bcc	10f
	mov	d1,d0
10:	mov	d0,(8,sp)
	movhu	d0,(a2)
	add	2,a2
	cmp	a1,a2
	bcs	6b
99:	ret	[d2,d3,a2,a3],28
90:	mov	d3,a0
	call	TONE_BUILD,[d2,d3,a2,a3],28
	ret	[d2,d3,a2,a3],28

# ---------------------------------------------------------------- v1.1b: per-film split toning
# The RGB gamma stage 0x604f6083 (frame 216; locals: (28,sp) O, (52,sp) R, (56,sp) C, (64/68/72,sp) R/G/B curve
# pointers, (32,sp) "table copied" flag) packs the curves into 256 x u32 tables (R | G<<10 | B<<20, 10-bit) at
# O+0x424 / O+0x824; O+1052 / O+1056 point at the active ones (0 = unused). The upload (0x604b5930) copies a bank
# only when C+100 bit 0 / bit 1 is set.
#
# st_gate replaces 7 B at 0x604f6139 ("cmp 0,d3; bne 0x604f6140; jmp 0x604f630f"): the cache-hit skip. A skip
# would keep the table bent for the previous film (the bend lives in the table, not in the curve pointers), so a
# single-curve request (R = G = B pointers, the only kind st_join bends) always takes the copy path. Curves that
# differ per channel (Cross Process, art) keep the stock skip.
	.global	st_gate
st_gate:
	cmp	0,d3
	beq	1f
	jmp	ST_COPY			# stock: copy
1:	mov	(64,sp),d0
	mov	(68,sp),d1
	cmp	d0,d1
	bne	2f
	mov	(72,sp),d1
	cmp	d0,d1
	bne	2f
	mov	1,d3				# single curve: copy anyway
	mov	d3,(32,sp)
	jmp	ST_COPY
2:	jmp	ST_SKIP			# stock skip

# st_join replaces 6 B at 0x604f62dc ("cmp 0,d2; beq 0x604f631b; mov (64,sp),d0"), the join after the three copier
# calls (all three paths arrive right after a call, so d0/d1/a0/a1 carry nothing). Same sp; d2/d3/a2/a3 kept.
# For a COLOR request without an art curve: C+100 |= 3 (upload this pass's tables), recognise the film from the
# shot's saturation (R+1076, sectors 1-4, as tn_tone), and bend each active bank with the film's K values.
	.global	st_join
st_join:
	movm	[d2,d3,a2,a3],(sp)
	add	-16,sp				# stage locals now at +32
	mov	(84,sp),a2			# R
	mov	(8,a2),d0
	cmp	0x000b0000,d0
	bne	90f
	mov	(960,a2),d0
	cmp	0,d0
	bne	90f
	mov	(88,sp),a0			# C
	mov	(100,a0),d0
	or	3,d0
	mov	d0,(100,a0)
	add	1076,a2
	movbu	(a2),d0
	and	15,d0
	movbu	(1,a2),d1
	and	15,d1
	asl	4,d1
	or	d1,d0
	mov	d0,d2				# sector 1 | sector 2 << 4
	movbu	(2,a2),d0
	and	15,d0
	movbu	(3,a2),d1
	and	15,d1
	asl	4,d1
	or	d1,d0				# sector 3 | sector 4 << 4
	clr	d3
	mov	FL_VALS,a0
1:	movbu	(a0),d1
	cmp	d2,d1
	bne	2f
	movbu	(1,a0),d1
	cmp	d0,d1
	beq	3f
2:	add	21,a0
	inc	d3
	cmp	NFILMS,d3
	bcs	1b
	bra	90f				# no film
3:	mov	d3,d0				# ST_K + 12 j: s16 KsR, KsG, KsB, KhR, KhG, KhB
	asl	2,d0
	mov	d0,d1
	add	d0,d0
	add	d1,d0
	mov	ST_K,a3
	add	d0,a3
	mov	(a3),d0
	mov	(4,a3),d1
	or	d1,d0
	mov	(8,a3),d1
	or	d1,d0
	cmp	0,d0
	beq	90f				# film without split toning
	mov	(60,sp),a2			# O
	mov	(1052,a2),a0
	cmp	0,a0
	beq	4f
	call	st_bend,[d2,d3,a2,a3],40
	mov	(60,sp),a2
4:	mov	(1056,a2),a0
	cmp	0,a0
	beq	90f
	call	st_bend,[d2,d3,a2,a3],40
90:	add	16,sp
	movm	(sp),[d2,d3,a2,a3]
	cmp	0,d2
	bne	91f
	jmp	ST_NOCACHE
91:	mov	(64,sp),d0
	jmp	ST_CACHE

# st_bend(a0 packed table, a3 film K record): caduceus bend28 with Tone Balance 0, per channel on 12-bit values
# (t = v << 2 | v >> 8): s = 4095 - t; ws = ((t*s>>12)*s)>>12; wh = ((t*t>>12)*s)>>12;
# t' = clamp(t + ((Ks*ws + Kh*wh) >> 9), 0, 4095), kept rising (running max); v' = t' >> 2.
# Locals: (0,sp) free; (4) channel shift; (8) Ks; (12) Kh; (16) running max; (20) end.
st_bend:
	clr	d0
	mov	d0,(4,sp)
	mov	a3,a1
5:	movhu	(a1),d0
	exth	d0
	mov	d0,(8,sp)
	movhu	(6,a1),d0
	exth	d0
	mov	d0,(12,sp)
	clr	d0
	mov	d0,(16,sp)
	mov	a0,a2
	mov	a0,d0
	add	1024,d0
	mov	d0,(20,sp)
6:	mov	(a2),d0
	mov	(4,sp),d1
	lsr	d1,d0
	and	1023,d0
	mov	d0,d1
	asl	2,d1
	lsr	8,d0
	or	d1,d0				# t
	mov	4095,d1
	sub	d0,d1				# s
	mov	d0,d2
	mul	d1,d2
	lsr	12,d2
	mul	d1,d2
	lsr	12,d2				# ws
	mov	d0,d3
	mul	d0,d3
	lsr	12,d3
	mul	d1,d3
	lsr	12,d3				# wh
	mov	(8,sp),d1
	mul	d1,d2
	mov	(12,sp),d1
	mul	d1,d3
	add	d3,d2
	asr	9,d2
	add	d2,d0
	cmp	0,d0
	bge	7f
	clr	d0
7:	cmp	4095,d0
	ble	8f
	mov	4095,d0
8:	mov	(16,sp),d1
	cmp	d1,d0
	bge	9f
	mov	d1,d0
9:	mov	d0,(16,sp)
	lsr	2,d0
	mov	(4,sp),d1
	asl	d1,d0
	mov	1023,d2
	asl	d1,d2
	not	d2
	mov	(a2),d3
	and	d2,d3
	or	d0,d3
	mov	d3,(a2)
	add	4,a2
	mov	(20,sp),d0
	cmp	d0,a2
	bcs	6b
	add	2,a1
	mov	(4,sp),d0
	add	10,d0
	mov	d0,(4,sp)
	cmp	30,d0
	bcs	5b
	ret	[d2,d3,a2,a3],40
