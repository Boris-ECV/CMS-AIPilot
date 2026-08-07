---
description: Process pending gates only
---
For every ticket in "Awaiting Gate": if the gate mode is auto, verify
each criterion in config/gates.yaml and pass/hold with evidence logged
as a ticket comment + gate_review metrics event. If manual, ensure the
gate report (templates/gate-report.md) is posted, then check ticket
comments for "GATE APPROVED" / "GATE REJECTED:" from the human and act
accordingly. Summarize results in 繁體中文.
