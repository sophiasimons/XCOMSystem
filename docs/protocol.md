# XCOM Host <-> Device Protocol (minimal)

This file describes a small, minimal protocol for communication between the host UI (via the bridge) and the device firmware.

Wire format (serial):
- Plain UTF-8 text lines ending with LF ("\n").
- Each line is a JSON object with at least a `type` field.

Example device -> host messages:
```json
{"type":"telemetry","temp_c":23.4,"voltage_v":3.30}
```

Example host -> device messages:
```json
{"type":"cmd","cmd":"led","args":{"state":"on"}}
```

Framing: use newline-delimited JSON. In C, build a line buffer and parse JSON when a '\n' is received.

Versioning: include a `version` field in production messages once stable.
