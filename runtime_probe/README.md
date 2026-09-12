# Runtime Probe

This standalone Atmosphère sysmodule tests whether `SetTimerEventEnabled(true)`
arms timer accounting. Once per application-process interval, it invokes
command 1501 with an exact one-byte value of 1, then command 1451, and retains
that session while polling commands 1453, 1454, 1455, and 1952. It never invokes
1452 or a settings command.

## Build and artifacts

Run `./run.sh` in this directory. It uses `devkitpro/devkita64` and produces:

- `nx_pctl_runtime_probe.nsp` — raw ExeFS NSP.
- `nx_pctl_runtime_probe.zip` — ready-to-copy SD-card layout.
- `out/atmosphere/contents/4200000000F04354/exefs.nsp` — packaged NSP.

## Install, start, and remove

Copy the ZIP's `atmosphere/` directory to the SD-card root. The final layout is:

```text
atmosphere/contents/4200000000F04354/exefs.nsp
atmosphere/contents/4200000000F04354/flags/boot2.flag
```

Atmosphère launches program ID `4200000000F04354` during `boot2`, so reboot
after copying it. Samples are appended every five seconds to
`sdmc:/switch/nx_pctl_runtime_<timestamp>.log` and flushed immediately.
`remaining_raw` and `spent_raw` preserve the returned 64-bit values; the probe
does not assume a time unit.

To disable automatic startup, remove or rename `boot2.flag`, then reboot. To
uninstall, remove `atmosphere/contents/4200000000F04354/` and reboot. There is
no live-unload control and no Tesla/Ultrahand dependency.

## Permissions and compatibility

The NPDM grants SD-card access plus these client services only:

- `fsp-srv` for the log file.
- `set:sys` to initialize libnx's HOS-version routing.
- `time:u` for log timestamps.
- `pctl:s` for commands 1501, 1451, and the four read-only timer queries.
- `pgl` for `pglGetApplicationProcessId()`.

The `pgl` result proves only that an application process exists; it does not
prove that the application owns visual foreground while HOME is open. Keep the
game visibly foreground during the experiment.

The build uses current devkitPro (`libnx 4.12.0-1`, `devkitA64 r29.2-1`). On HOS
22.5, libnx routes `pgl` through TIPC. The principal hardware uncertainty is
whether a custom sysmodule's `pctl:s` session observes the same global timer
state as Pctl Manager. Initialization and query Result codes remain in the log.
