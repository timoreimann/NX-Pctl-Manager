#!/usr/bin/env python3
"""Compare unpaired and paired nx_pctl_runtime_*.log captures (read-only)."""

import argparse
import re
from pathlib import Path


BLOB_SIZE = 0x44


def fields(line):
    return dict(part.split("=", 1) for part in line.split() if "=" in part)


def parse_log(path):
    capture = {"header": None, "header_line": None,
               "settings": {}, "pairing": {}, "samples": {}}
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if line.startswith("nx_pctl_runtime_probe "):
            if capture["header"] is not None:
                raise ValueError(f"{path}:{number}: multiple runs in one file")
            capture["header"] = fields(line)
            capture["header_line"] = line
            continue
        data = fields(line)
        if line.startswith("event=play_timer_settings "):
            blob = data.get("blob", "")
            if data.get("145601_rc") == "0x00000000":
                if len(blob) != BLOB_SIZE * 2 or not re.fullmatch(r"[0-9a-fA-F]+", blob):
                    raise ValueError(f"{path}:{number}: expected exactly 0x44 blob bytes")
                data["blob_bytes"] = bytes.fromhex(blob)
            capture["settings"][int(data["sample"])] = data
        elif line.startswith("event=pairing_state "):
            capture["pairing"][int(data["sample"])] = data
        elif line.startswith("sample="):
            capture["samples"][int(data["sample"])] = data
    if capture["header"] is None:
        raise ValueError(f"{path}: missing probe header")
    return capture


def snapshot(capture, reason):
    matches = [data for _, data in sorted(capture["settings"].items())
               if data.get("reason") == reason]
    if not matches:
        raise ValueError(f"missing {reason} settings snapshot")
    settings = matches[0]
    sample = int(settings["sample"])
    if sample not in capture["pairing"] or sample not in capture["samples"]:
        raise ValueError(f"missing pairing or timer sample for {reason} sample {sample}")
    return settings, capture["pairing"][sample], capture["samples"][sample]


def format_blob(blob):
    return blob.hex().upper() if blob is not None else "unavailable"


def decode(blob):
    if blob is None:
        return ["  decoded settings: unavailable"]
    lines = ["  header 0x00..0x03: " + blob[:4].hex(" ").upper()
             + " (candidate fields; semantics unconfirmed)",
             "  candidate default/daily 0x04..0x09: " + blob[4:10].hex(" ").upper(),
             "  unknown/global 0x0A..0x0B: " + blob[10:12].hex(" ").upper()]
    for day in range(7):
        offset = 0x0C + 8 * day
        record = blob[offset:offset + 8]
        lines.append(f"  weekday {day} 0x{offset:02X}..0x{offset + 7:02X}: "
                     f"raw={record.hex(' ').upper()} "
                     f"b0_1={record[:2].hex().upper()} "
                     f"b2_3={record[2:4].hex().upper()} "
                     f"b4=0x{record[4]:02X} b5=0x{record[5]:02X} "
                     f"b6_7_u16le={int.from_bytes(record[6:8], 'little')} "
                     "(candidate limit; semantics unconfirmed)")
    return lines


def show_snapshot(label, reason, capture):
    settings, pairing, sample = snapshot(capture, reason)
    blob = settings.get("blob_bytes")
    print(f"{label} {reason}: sample={settings['sample']} time={settings.get('time')} "
          f"PID={settings.get('application_pid')} "
          f"145601_rc={settings.get('145601_rc')}")
    updated = pairing.get("last_updated_posix_raw", "unavailable")
    if updated.isdecimal():
        updated += f" (0x{int(updated):X})"
    print(f"  pairing_active={pairing.get('pairing_active')} "
          f"1403_rc={pairing.get('1403_rc')} "
          f"1406_rc={pairing.get('1406_rc')} "
          f"last_updated_posix_raw={updated}")
    print(f"  enabled={sample.get('enabled')} 1453_rc={sample.get('1453_rc')} "
          f"remaining_raw={sample.get('remaining_raw')} 1454_rc={sample.get('1454_rc')} "
          f"restricted={sample.get('restricted')} 1455_rc={sample.get('1455_rc')} "
          f"spent_raw={sample.get('spent_raw')} 1952_rc={sample.get('1952_rc')}")
    print(f"  blob={format_blob(blob)}")
    print("\n".join(decode(blob)))
    return blob


def show_differences(reason, unpaired, paired):
    print(f"{reason} 0x44-byte differences:")
    if unpaired is None or paired is None:
        print("  unavailable (145601 failed in at least one capture)")
        return None
    differences = [(offset, left, right) for offset, (left, right)
                   in enumerate(zip(unpaired, paired)) if left != right]
    for offset, left, right in differences:
        print(f"  offset 0x{offset:02X}: unpaired=0x{left:02X} paired=0x{right:02X}")
    if not differences:
        print("  none")
    return bool(differences)


def activity(capture):
    samples = [row for _, row in sorted(capture["samples"].items())]
    intervals = []
    current = []
    for row in samples:
        valid = row.get("application_process_present") == "1" and all(
            row.get(key) == "0x00000000"
            for key in ("1453_rc", "1454_rc", "1455_rc", "1952_rc"))
        if not valid or (current and row.get("application_pid") != current[-1].get("application_pid")):
            if current:
                intervals.append(current)
                current = []
        if valid:
            current.append(row)
    if current:
        intervals.append(current)
    valid = [row for interval in intervals for row in interval]
    if not valid:
        return "indeterminate", 0, None
    changed = any(
        int(later["spent_raw"], 16) > int(earlier["spent_raw"], 16)
        or int(later["remaining_raw"], 16) < int(earlier["remaining_raw"], 16)
        for interval in intervals for earlier, later in zip(interval, interval[1:]))
    restricted = any(row.get("restricted") == "1" for row in valid)
    accounting = "observed" if changed else (
        "not observed" if any(len(interval) > 1 for interval in intervals) else "indeterminate")
    first, last = valid[0].get("time"), valid[-1].get("time")
    return accounting, len(valid), (
        f"{first}..{last}; intervals={len(intervals)}; restricted_ever={int(restricted)}")


def compare(unpaired_path, paired_path):
    captures = [parse_log(unpaired_path), parse_log(paired_path)]
    for label, capture in zip(("unpaired", "paired"), captures):
        print(f"{label} header: {capture['header_line']}")
    if captures[0]["header"].get("hos") != captures[1]["header"].get("hos"):
        print("WARNING: HOS versions differ")
    differences = []
    for reason in ("startup", "application_started"):
        blobs = [show_snapshot(label, reason, capture)
                 for label, capture in zip(("unpaired", "paired"), captures)]
        differences.append(show_differences(reason, *blobs))
    states = [activity(capture) for capture in captures]
    for label, (state, count, span) in zip(("unpaired", "paired"), states):
        print(f"{label} application samples: {count}; accounting={state}; span={span}")
    blob_differs = any(x is True for x in differences)
    blob_known = all(x is not None for x in differences)
    print(f"Summary: 0x44 settings blob differs={blob_differs}"
          if blob_known else "Summary: 0x44 settings comparison incomplete")
    pairing_keys = ("1403_rc", "pairing_active", "1406_rc", "last_updated_posix_raw")
    pairing_differs = any(
        any(snapshot(captures[0], reason)[1].get(key) !=
            snapshot(captures[1], reason)[1].get(key) for key in pairing_keys)
        for reason in ("startup", "application_started"))
    timer_keys = ("1453_rc", "enabled", "1454_rc", "remaining_raw",
                  "1455_rc", "restricted", "1952_rc", "spent_raw")
    timer_snapshot_differs = any(
        snapshot(captures[0], "application_started")[2].get(key) !=
        snapshot(captures[1], "application_started")[2].get(key)
        for key in timer_keys)
    runtime_differs = timer_snapshot_differs or states[0][0] != states[1][0]
    print(f"Summary: observed pairing-related state differs={pairing_differs}")
    print(f"Summary: first application timer readouts differ={timer_snapshot_differs}")
    if blob_known:
        same_capture_type = all(captures[0]["header"].get(key) == captures[1]["header"].get(key)
                                for key in ("hos", "experiment"))
        print(f"Summary: only observed pairing-related state differs="
              f"{pairing_differs and not blob_differs and not runtime_differs and same_capture_type}")
    print(f"Summary: accounting observed only in paired capture="
          f"{states[0][0] == 'not observed' and states[1][0] == 'observed'}")
    print(f"Summary: both settings and runtime behavior differ="
          f"{blob_differs and runtime_differs}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("unpaired", type=Path, help="unpaired baseline runtime log")
    parser.add_argument("paired", type=Path, help="officially paired runtime log")
    args = parser.parse_args()
    try:
        compare(args.unpaired, args.paired)
    except (OSError, KeyError, ValueError) as error:
        parser.exit(2, f"comparison failed: {error}\n")


if __name__ == "__main__":
    main()
