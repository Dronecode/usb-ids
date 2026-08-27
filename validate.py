#!/usr/bin/env python3
"""Validate usb-ids.yaml, the Dronecode USB ID registry.

Checks structure, field formats, PID uniqueness (case-insensitive),
px4_vendor slug uniqueness, and block allocation: every non-legacy PID sits
inside one of its manufacturer's claimed 16-PID blocks, and no block holds
another manufacturer's PID. Prints one error per line and exits 1 on any
violation, 0 when the registry is valid.

Only dependency: PyYAML.
"""

import re
import sys

import yaml

PID_RE = re.compile(r"^0x[0-9A-F]{4}$")
VID_RE = re.compile(r"^0x[0-9A-F]{4}$")
BLOCK_RE = re.compile(r"^0x[0-9A-F]{3}0$")
PX4_VENDOR_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

TOP_KEYS = {"vid", "vendor_string", "manufacturers"}
MFR_REQUIRED = {"name", "contact", "pids"}
MFR_OPTIONAL = {"px4_vendor", "blocks"}
PID_REQUIRED = {"pid", "board", "date"}
PID_OPTIONAL = {"legacy"}

# Assignments predating the block policy. Maintainer-set: extending this set
# is a deliberate edit here, not something a PID request can grant itself.
LEGACY_PIDS = {"0x0001", "0x0002", "0x0003"}
LEGACY_CUTOFF = "2026-09-01"


def validate(doc):
    errors = []

    def err(msg):
        errors.append(msg)

    if not isinstance(doc, dict):
        return ["top level: expected a mapping"]

    for key in sorted(set(doc) - TOP_KEYS):
        err(f"top level: unknown field '{key}'")
    for key in sorted(TOP_KEYS - set(doc)):
        err(f"top level: missing field '{key}'")

    vid = doc.get("vid")
    if vid is not None and (not isinstance(vid, str) or not VID_RE.match(vid)):
        err(f"vid: '{vid}' is not a quoted 0xXXXX uppercase hex string")

    vendor_string = doc.get("vendor_string")
    if vendor_string is not None and (
        not isinstance(vendor_string, str) or not vendor_string.strip()
    ):
        err("vendor_string: must be a non-empty string")

    manufacturers = doc.get("manufacturers")
    if manufacturers is None:
        return errors
    if not isinstance(manufacturers, list):
        err("manufacturers: expected a list")
        return errors

    seen_pids = {}  # normalized pid -> manufacturer name
    seen_vendors = {}  # px4_vendor -> manufacturer name
    seen_blocks = {}  # block start -> manufacturer name
    assigned = []  # (pid as int, pid as written, manufacturer name)

    for i, mfr in enumerate(manufacturers):
        where = f"manufacturers[{i}]"
        if not isinstance(mfr, dict):
            err(f"{where}: expected a mapping")
            continue
        name = mfr.get("name")
        if isinstance(name, str) and name.strip():
            where = f"manufacturer '{name}'"
        else:
            err(f"{where}: missing or empty 'name'")

        for key in sorted(set(mfr) - MFR_REQUIRED - MFR_OPTIONAL):
            err(f"{where}: unknown field '{key}'")
        for key in sorted(MFR_REQUIRED - set(mfr)):
            err(f"{where}: missing field '{key}'")

        contact = mfr.get("contact")
        if "contact" in mfr and (
            not isinstance(contact, str) or not EMAIL_RE.match(contact)
        ):
            err(f"{where}: 'contact' must be an email address")

        px4_vendor = mfr.get("px4_vendor")
        if px4_vendor is not None:
            if not isinstance(px4_vendor, str) or not PX4_VENDOR_RE.match(px4_vendor):
                err(
                    f"{where}: px4_vendor '{px4_vendor}' must be lowercase "
                    "letters, digits, or hyphens"
                )
            elif px4_vendor in seen_vendors:
                err(
                    f"{where}: px4_vendor '{px4_vendor}' already used by "
                    f"'{seen_vendors[px4_vendor]}'"
                )
            else:
                seen_vendors[px4_vendor] = name

        # Blocks are all 16 wide and 16-aligned, so two of them overlap only
        # if they share a start value: unique starts means no overlap.
        blocks = mfr.get("blocks")
        mfr_blocks = set()
        if "blocks" in mfr:
            if not isinstance(blocks, list) or not blocks:
                err(f"{where}: 'blocks' must be a non-empty list")
            else:
                for block in blocks:
                    if not isinstance(block, str) or not BLOCK_RE.match(block):
                        err(
                            f"{where}: block '{block}' is not a quoted 0xXXX0 "
                            "uppercase hex string; a block start must end in 0 "
                            "(16-aligned)"
                        )
                        continue
                    if block in mfr_blocks:
                        err(f"{where}: block '{block}' listed twice")
                        continue
                    mfr_blocks.add(block)
                    if block in seen_blocks:
                        err(
                            f"{where}: block '{block}' already claimed by "
                            f"'{seen_blocks[block]}'"
                        )
                    else:
                        seen_blocks[block] = name

        pids = mfr.get("pids")
        if "pids" not in mfr:
            continue
        if not isinstance(pids, list) or not pids:
            err(f"{where}: 'pids' must be a non-empty list")
            continue

        for j, entry in enumerate(pids):
            pwhere = f"{where} pids[{j}]"
            if not isinstance(entry, dict):
                err(f"{pwhere}: expected a mapping")
                continue

            for key in sorted(set(entry) - PID_REQUIRED - PID_OPTIONAL):
                err(f"{pwhere}: unknown field '{key}'")
            for key in sorted(PID_REQUIRED - set(entry)):
                err(f"{pwhere}: missing field '{key}'")

            pid = entry.get("pid")
            pid_ok = False
            if "pid" in entry:
                if not isinstance(pid, str) or not PID_RE.match(pid):
                    err(
                        f"{pwhere}: pid '{pid}' is not a quoted 0xXXXX "
                        "uppercase hex string"
                    )
                else:
                    pid_ok = True
                    pwhere = f"{where} pid {pid}"
                    norm = pid.lower()
                    if norm in seen_pids:
                        err(
                            f"{pwhere}: duplicate, already assigned to "
                            f"'{seen_pids[norm]}'"
                        )
                    else:
                        seen_pids[norm] = name
                        assigned.append((int(pid, 16), pid, name))

            board = entry.get("board")
            if "board" in entry and (not isinstance(board, str) or not board.strip()):
                err(f"{pwhere}: 'board' must be a non-empty string")

            date = entry.get("date")
            # PyYAML may parse unquoted dates as datetime.date
            date_str = date.isoformat() if hasattr(date, "isoformat") else date
            date_ok = isinstance(date_str, str) and bool(DATE_RE.match(date_str))
            if "date" in entry and not date_ok:
                err(f"{pwhere}: date '{date}' must be YYYY-MM-DD")

            legacy = entry.get("legacy")
            if "legacy" in entry:
                if legacy is not True:
                    err(f"{pwhere}: 'legacy' must be true when present")
                elif not (pid_ok and pid in LEGACY_PIDS):
                    err(
                        f"{pwhere}: 'legacy' is maintainer-set only; this pid "
                        "is not in the frozen legacy set"
                    )
                elif date_ok and date_str >= LEGACY_CUTOFF:
                    err(
                        f"{pwhere}: 'legacy' is only for assignments predating "
                        f"the block policy (date before {LEGACY_CUTOFF})"
                    )

            # Skip entries whose pid already failed the format check.
            if pid_ok and legacy is not True:
                start = f"0x{int(pid, 16) & ~0xF:04X}"
                if start not in mfr_blocks:
                    err(
                        f"{pwhere}: outside {name}'s claimed blocks; claim "
                        f"block '{start}' in 'blocks' or move the pid into a "
                        "claimed block"
                    )

    # A claimed block must not hold another manufacturer's pid, legacy ones
    # included; this is what keeps the pre-policy 0x0000-0x000F range frozen.
    for pid_int, pid, owner in assigned:
        start = f"0x{pid_int & ~0xF:04X}"
        holder = seen_blocks.get(start)
        if holder is not None and holder != owner:
            err(
                f"manufacturer '{holder}': block '{start}' contains pid "
                f"{pid} assigned to '{owner}'"
            )

    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "usb-ids.yaml"
    try:
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        print(f"error: cannot load {path}: {e}", file=sys.stderr)
        return 1

    errors = validate(doc)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if errors:
        print(f"{path}: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"{path}: valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
