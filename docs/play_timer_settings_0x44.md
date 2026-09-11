# PlayTimerSettings 0x44-byte Analysis

## Scope and provenance

This is analysis only. No unknown `PlayTimerSettings` value should be written
until the runtime-probe baseline is complete.

The current interpretation entered the repository in initial commit `9cba130`.
Its comment says it was decoded from a working HOS 22.1 console configured by
the companion app, but neither the source dump nor the referenced `CLAUDE.md`
is committed. Current libnx exposes no `PlayTimerSettings` type or get/set
wrapper; the repository's `u16[34]` interpretation is local reverse engineering.

Four HOS 22.5 captures (`nx_pctl_probe_20260911_104456.txt` through
`...105156.txt`) returned identical bytes:

```text
00 01 01 00 00 00 00 00 00 00 00 00  00 00 00 06 00 01 02 00
00 00 00 06 00 01 02 00  00 00 00 06 00 01 02 00
00 00 00 06 00 01 02 00  00 00 00 06 00 01 02 00
00 00 00 06 00 01 02 00  00 00 00 06 00 01 02 00
```

## Most likely structural layout

The cleanest fit is a 12-byte prefix followed by seven complete 8-byte day
records. Day record `d` begins at `B = 0x0C + 8*d`.

| Offset | Size | HOS 22.5 value | Current interpretation | Assessment |
|---|---:|---|---|---|
| `0x00` | 1 | `00` | Low byte of `c[0]=0x0101`; writer sends `01` | Unknown global flag. The observed/read-back value contradicts the writer. Because command 1453 is true with this byte zero, it is not required for `IsPlayTimerEnabled`. Low semantic confidence. |
| `0x01` | 1 | `01` | High byte of `c[0]`, called “enabled & active” | Plausible global settings-enable flag, but “active” is unsupported by runtime results. Low confidence. |
| `0x02–03` | 2 | `01 00` | `c[1]=1`, otherwise unknown | Plausible schedule-valid or per-day-mode field. Low confidence. |
| `0x04–0B` | 8 | all zero | Reserved portion of `c[2..6]` | Unknown prefix fields. No evidence ties them to dates or lifecycle. Low confidence. |
| `B+0` | 2 | `00 00` every day | Misattributed to prefix/previous trailing field | Likely the HOS-21-added per-day field, based on size evolution. Meaning unknown; a validity or second schedule value is possible but unproven. Medium structural, zero semantic confidence. |
| `B+2` | 2 | `00 06` every day | Little-endian `0x0600`, unknown constant | Could be two byte-sized time components; `06:00` is a plausible reset/bedtime-related value. This is only a hypothesis. Low confidence. |
| `B+4` | 2 | `00 01` every day | Little-endian `0x0100`; nonzero means configured day | Composite value correlates with an enabled daily limit. Individual byte meanings remain unknown. Medium confidence. |
| `B+6` | 2 | `02 00` every day | Little-endian daily limit in minutes | Matches the configured two-minute limit for every day. High confidence. |

The record bases are `0x0C`, `0x14`, `0x1C`, `0x24`, `0x2C`, `0x34`, and
`0x3C`. The source claims Sun-through-Sat ordering based on an uncommitted known
configuration comparison; treat that ordering as medium confidence.

The current comment instead describes a 14-byte prefix and records starting at
`0x0E`, leaving the final record “truncated.” That structure is almost certainly
wrong. Its decoder still lands on the correct minute offsets (`B+6`), and its
writer happens to leave `B+0` zero while writing `B+2`, `B+4`, and `B+6`.

## Version evidence

| HOS range | IPC payload | Structural inference |
|---|---:|---|
| Through 17.x | `0x34`, alignment 2 | `10 + 7*6` |
| 18.x–20.x | `0x36` | `12 + 7*6` |
| 21.x+ | `0x44` | `12 + 7*8` |

The HOS-21 increase is exactly two bytes per weekday. This supports the record
model but does not identify the new field's meaning.

## Concepts not established by this blob

- Timer enabled/active: header bytes `0x01`/`0x02` and `B+4` are candidates,
  but running lifecycle is more plausibly maintained by commands 1451/1452 and
  the remaining/spent-time state.
- Alarm versus forced restriction: command 1458 has a separate debug setter
  (1953), while bedtime has separate query commands. Do not assign those
  meanings to a settings byte without an official-setting diff.
- Event enablement: command 1501 controls this separately on HOS 20+.
- Date/day validity: only weekday position is supported. `B+0` is unknown.
- Timer lifecycle: no field is currently evidenced as start/stop state.

The strongest lead is offset `0x00`: the writer sends `01 01` at offsets
`0x00–01`, while HOS 22.5 reads back `00 01`. This could be service
normalization, a version change, or a mistaken original interpretation. It is
not yet a fix proposal.

## One-variable experiment matrix

Run the Track A baseline first. Then capture settings made through Nintendo's
official UI/app, changing only one concept per capture:

1. Two minutes/all days, bedtime off, Suspend Software off.
2. Toggle only Suspend Software.
3. Toggle only bedtime at a fixed time.
4. Change bedtime from 21:00 to 21:15.
5. If exposed, change only the reset time from 06:00 to 07:00.
6. Change one weekday from two to three minutes.
7. Switch all-days to per-day mode while keeping all seven limits equal.
8. Remove only the daily limit while preserving bedtime/policy.
9. Pair every capture with the same foreground runtime sample sequence.
10. Only after those comparisons, submit an exact captured blob unchanged as a
    control. A later byte-0-only test should restore that captured blob afterward.

Do not mutate `B+0` or any other unknown field before a native-setting diff gives
it a defensible meaning.

## References

- [Switchbrew pctl commands and HOS-21 payload](https://switchbrew.org/wiki/Parental_Control_services)
- [HOS 18 IPC change: 0x36-byte commands](https://switchbrew.org/wiki/18.0.0)
- [HOS 21 IPC change: 0x36 to 0x44](https://switchbrew.org/wiki/21.0.0)
- [Historical SwIPC 0x34-byte type](https://reswitched.github.io/SwIPC/types.html)
- [Current libnx pctl header](https://github.com/switchbrew/libnx/blob/master/nx/include/switch/services/pctl.h)
- [Current libnx pctl implementation](https://github.com/switchbrew/libnx/blob/master/nx/source/services/pctl.c)
- [Repository origin of the interpretation](https://github.com/tailiang2008/NX-Pctl-Manager/commit/9cba13056d55b7b45e2abd04bd7b7243e13ed059)
