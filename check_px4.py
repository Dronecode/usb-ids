#!/usr/bin/env python3
"""Check usb-ids.yaml against a PX4-Autopilot checkout.

Usage: check_px4.py <px4-autopilot-dir> [usb-ids.yaml]

A PX4 board defconfig matches its registry entry when it lives at
boards/<px4_board>/nuttx-config/*/defconfig and its CONFIG_CDCACM_VENDORID,
CONFIG_CDCACM_PRODUCTID (hex-int compares) and CONFIG_CDCACM_VENDORSTR
(exact: the registry vendor_string, or the manufacturer's
usb_vendor_string, which defaults to its name) agree with the registry.

Both directions are checked: every entry with px4_board must match the
defconfigs in that directory, and every PX4 defconfig using the registry VID
must belong to some entry's px4_board. A px4_board whose directory does not
exist in PX4 yet is a notice, not an error, so a registry entry can land
before its board PR. Prints one line per finding and exits 1 on any error.

Only dependency: PyYAML.
"""

import sys
from pathlib import Path

from validate import load, validate

DEFCONFIG_GLOB = "nuttx-config/*/defconfig"
KEYS = ("CONFIG_CDCACM_VENDORID", "CONFIG_CDCACM_PRODUCTID", "CONFIG_CDCACM_VENDORSTR")


def read_defconfig(path):
    """Return the CDCACM settings of a defconfig, strings unquoted."""
    values = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        key, sep, value = line.partition("=")
        if sep and key in KEYS:
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
            values[key] = value
    return values


def hex_int(value):
    try:
        return int(value, 16)
    except (TypeError, ValueError):
        return None


def check(doc, px4_dir):
    """Return (errors, notices) comparing the registry to PX4's boards/."""
    errors, notices = [], []
    boards_dir = px4_dir / "boards"
    vid = int(doc["vid"], 16)

    # px4_board -> (pid, accepted vendor strings)
    entries = {}
    for mfr in doc["manufacturers"]:
        strings = {doc["vendor_string"], mfr.get("usb_vendor_string", mfr["name"])}
        for entry in mfr["pids"]:
            if "px4_board" in entry:
                entries[entry["px4_board"]] = (entry["pid"], strings)

    # board -> [(defconfig path relative to PX4, settings)] for our VID only
    px4_boards = {}
    for path in sorted(boards_dir.glob(f"*/*/{DEFCONFIG_GLOB}")):
        values = read_defconfig(path)
        if hex_int(values.get("CONFIG_CDCACM_VENDORID")) != vid:
            continue
        board = "/".join(path.relative_to(boards_dir).parts[:2])
        rel = path.relative_to(px4_dir).as_posix()
        px4_boards.setdefault(board, []).append((rel, values))

    for board, (pid, strings) in sorted(entries.items()):
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
        for rel, values in defconfigs:
            product = values.get("CONFIG_CDCACM_PRODUCTID")
            if hex_int(product) != int(pid, 16):
                errors.append(
                    f"{rel}: CONFIG_CDCACM_PRODUCTID={product} but the "
                    f"registry assigns {pid} to {board}"
                )
            vendor_str = values.get("CONFIG_CDCACM_VENDORSTR")
            if vendor_str not in strings:
                expected = " or ".join(f'"{s}"' for s in sorted(strings))
                found = "unset" if vendor_str is None else f'"{vendor_str}"'
                errors.append(
                    f"{rel}: CONFIG_CDCACM_VENDORSTR is {found}, "
                    f"expected {expected}"
                )

    for board, defconfigs in sorted(px4_boards.items()):
        if board not in entries:
            for rel, _ in defconfigs:
                errors.append(
                    f"{rel}: uses VID {doc['vid']} but no registry entry "
                    f"has px4_board '{board}'"
                )

    return errors, notices


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
        errors, notices = check(doc, px4_dir)
        for n in notices:
            print(f"notice: {n}")
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if errors:
        print(f"{path}: {len(errors)} error(s) against {px4_dir}", file=sys.stderr)
        return 1
    print(f"{path}: matches {px4_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
