# Dronecode USB ID Registry

The Dronecode Foundation owns USB vendor ID **`0x3643`** ("Dronecode
Project, Inc.") and assigns product IDs (PIDs) to member companies building
Pixhawk/PX4-compatible hardware. This repository is the single source of
truth for those assignments: [`usb-ids.yaml`](usb-ids.yaml).

PX4-Autopilot CI checks board definitions against this registry, so a board
using VID `0x3643` cannot merge upstream with an unregistered PID or a PID
belonging to another manufacturer.

PIDs are assigned in blocks of 16: your first request claims an aligned
block (`0xNNN0`-`0xNNNF`) and every PID you are assigned comes from inside
it. Claim a block when you have hardware to name, not in advance; when a
block fills up, claim another.

## Requesting a PID

1. Open a pull request adding your entry to `usb-ids.yaml` under your
   manufacturer block (create one if it's your first request):

   ```yaml
   - name: Acme Robotics
     px4_vendor: acme          # your directory under boards/ in PX4-Autopilot
     contact: usb@acme.example
     blocks: ["0x0070"]        # 16 PIDs, 0x0070-0x007F
     pids:
       - pid: "0x0070"
         board: Acme FC1
         date: 2026-07-10
   ```

2. CI validates the file (format, uniqueness). A maintainer confirms your
   Dronecode Foundation membership and merges. Assignments are at maintainer
   discretion.

Pick the lowest free block unless you have a reason not to; any free
aligned block is fine. One entry per PID. PID values are hexadecimal:
after `"0x0039"` comes `"0x003A"`, not `"0x0040"`. If you can't open a
PR, use the [PID request issue form](../../issues/new/choose).

## Field reference

| Field | Rules |
|---|---|
| `pid` | `"0x"` + 4 uppercase hex digits, quoted, globally unique |
| `board` | Board name |
| `date` | Assignment date, `YYYY-MM-DD` |
| `contact` | Email address for the manufacturer |
| `px4_vendor` | Your vendor directory name in the PX4 `boards/` tree. Optional until you upstream a board; **required before your first PX4-Autopilot board PR**, otherwise PX4 CI will reject it. |
| `blocks` | List of claimed block starts, `"0x"` + 4 uppercase hex digits ending in `0`; each covers 16 PIDs (`0xNNN0`-`0xNNNF`), globally unique. Required before any non-legacy PID can be assigned. |
| `legacy` | `true` on assignments that predate the block policy (before 2026-09). Maintainer-set, not for new requests. |

## Validation

```sh
pip install pyyaml
python3 validate.py usb-ids.yaml
```

Runs automatically on every PR and push to `main`.

Note for maintainers: PX4 CI (including release branches carrying older
copies of `check_usb_ids.py`) fetches this file from `main` at check time,
so schema changes must stay backward compatible: adding fields is fine,
renaming or removing them breaks deployed checkers.
