# Dronecode USB ID Registry

The Dronecode Foundation owns USB vendor ID **`0x3643`** ("Dronecode
Project, Inc.") and assigns product IDs (PIDs) to member companies building
Pixhawk/PX4-compatible hardware. This repository is the single source of
truth for those assignments: [`usb-ids.yaml`](usb-ids.yaml).

PX4-Autopilot CI checks board definitions against this registry, so a board
using VID `0x3643` cannot merge upstream with an unregistered PID or a PID
belonging to another manufacturer.

There are no reservations: PIDs are assigned to real boards. Request one
when you have hardware to name.

## Requesting a PID

1. Open a pull request adding your entry to `usb-ids.yaml` under your
   manufacturer block (create one if it's your first request):

   ```yaml
   - name: Acme Robotics
     px4_vendor: acme          # your directory under boards/ in PX4-Autopilot
     contact: usb@acme.example
     pids:
       - pid: "0x0070"
         board: Acme FC1
         date: 2026-07-10
   ```

2. CI validates the file (format, uniqueness). A maintainer confirms your
   Dronecode Foundation membership and merges. Assignments are at maintainer
   discretion.

Pick the lowest free PID; one entry per PID. If you can't open a PR, use
the [PID request issue form](../../issues/new/choose).

## Field reference

| Field | Rules |
|---|---|
| `pid` | `"0x"` + 4 uppercase hex digits, quoted, globally unique |
| `board` | Board name |
| `date` | Assignment date, `YYYY-MM-DD` |
| `contact` | Email address for the manufacturer |
| `px4_vendor` | Your vendor directory name in the PX4 `boards/` tree. Optional until you upstream a board; **required before your first PX4-Autopilot board PR**, otherwise PX4 CI will reject it. |

## Validation

```sh
pip install pyyaml
python3 validate.py usb-ids.yaml
```

Runs automatically on every PR and push to `main`.
