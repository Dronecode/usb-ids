#!/usr/bin/env python3
"""Check usb-ids.yaml against a PX4-Autopilot checkout.

Usage: check_px4.py <px4-autopilot-dir> [usb-ids.yaml]

A PX4 board defconfig at boards/<px4_board>/nuttx-config/*/defconfig whose
CONFIG_CDCACM_VENDORID is the registry VID must set CONFIG_CDCACM_PRODUCTID
to that entry's PID (hex-int compares).

Both directions are checked: every entry with px4_board must match the
defconfigs in that directory, and every PX4 defconfig using the registry VID
must belong to some entry's px4_board. A px4_board whose directory does not
exist in PX4 yet is a notice, not an error, so a registry entry can land
before its board PR. A PX4 path with no boards/ directory, or with no
defconfig using the registry VID, is an error, so an empty checkout cannot
pass. Prints one line per finding and exits 1 on any error.

Only dependency: PyYAML.
"""

import sys
from pathlib import Path

from validate import load, validate

DEFCONFIG_GLOB = "nuttx-config/*/defconfig"
KEYS = ("CONFIG_CDCACM_VENDORID", "CONFIG_CDCACM_PRODUCTID")


def read_defconfig(path):
    """Return the CDCACM VID and PID settings of a defconfig."""
    values = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        key, sep, value = line.partition("=")
        if sep and key in KEYS:
            values[key] = value
    return values


def hex_int(value):
    try:
        return int(value, 16)
    except (TypeError, ValueError):
        return None


def check(doc, px4_dir):
    """Return (errors, notices, defconfigs checked, boards checked)."""
    errors, notices = [], []
    boards_dir = px4_dir / "boards"
    vid = int(doc["vid"], 16)

    # px4_board -> pid
    entries = {}
    for mfr in doc["manufacturers"]:
        for entry in mfr["pids"]:
            if "px4_board" in entry:
                entries[entry["px4_board"]] = entry["pid"]

    # board -> [(defconfig path relative to PX4, settings)] for our VID only
    px4_boards = {}
    for path in sorted(boards_dir.glob(f"*/*/{DEFCONFIG_GLOB}")):
        values = read_defconfig(path)
        if hex_int(values.get("CONFIG_CDCACM_VENDORID")) != vid:
            continue
        board = "/".join(path.relative_to(boards_dir).parts[:2])
        rel = path.relative_to(px4_dir).as_posix()
        px4_boards.setdefault(board, []).append((rel, values))

    # PX4 ships boards on this VID, so finding none means a wrong or empty
    # checkout, not a clean result.
    if not px4_boards:
        errors.append(
            f"no defconfig under {boards_dir} sets "
            f"CONFIG_CDCACM_VENDORID={doc['vid']}; not a PX4 checkout?"
        )
        return errors, notices, 0, 0

    checked_boards = 0
    for board, pid in sorted(entries.items()):
        if not (boards_dir / board).is_dir():
            notices.append(
                f"pid {pid}: boards/{board}/ not in PX4 yet; checked once "
                "the board is upstream"
            )
            continue
        defconfigs = px4_boards.get(board)
        if not defconfigs:
            errors.append(
                f"pid {pid}: no defconfig under boards/{board}/ sets "
                f"CONFIG_CDCACM_VENDORID={doc['vid']}"
            )
            continue
        checked_boards += 1
        for rel, values in defconfigs:
            product = values.get("CONFIG_CDCACM_PRODUCTID")
            if hex_int(product) != int(pid, 16):
                errors.append(
                    f"{rel}: CONFIG_CDCACM_PRODUCTID={product} but the "
                    f"registry assigns {pid} to {board}"
                )

    for board, defconfigs in sorted(px4_boards.items()):
        if board not in entries:
            for rel, _ in defconfigs:
                errors.append(
                    f"{rel}: uses VID {doc['vid']} but no registry entry "
                    f"has px4_board '{board}'"
                )

    checked = sum(len(d) for d in px4_boards.values())
    return errors, notices, checked, checked_boards


def main():
    if len(sys.argv) not in (2, 3):
        print(__doc__.splitlines()[2], file=sys.stderr)
        return 2
    px4_dir = Path(sys.argv[1])
    path = sys.argv[2] if len(sys.argv) > 2 else "usb-ids.yaml"
    if not (px4_dir / "boards").is_dir():
        print(f"error: {px4_dir}/boards is not a directory", file=sys.stderr)
        return 1

    ok, doc = load(path)
    if not ok:
        return 1
    # The cross-check trusts the registry's structure; stop if it is invalid.
    errors = validate(doc)
    if not errors:
        errors, notices, checked, boards = check(doc, px4_dir)
        for n in notices:
            print(f"notice: {n}")
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if errors:
        print(f"{path}: {len(errors)} error(s) against {px4_dir}", file=sys.stderr)
        return 1
    print(
        f"{path}: matches {px4_dir}, checked {checked} defconfig(s) "
        f"across {boards} mapped board(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
