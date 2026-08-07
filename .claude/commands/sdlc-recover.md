---
description: Run the recovery procedure (stale locks, orphan branches, stuck gates)
---
Execute docs/00-handover.md recovery procedure only: clear locks older
than 60 minutes (comment [RECOVERY] on each), inventory branches whose
ticket is not In Progress (set those tickets Blocked with the branch
name noted — never delete branches), re-verify tickets stuck in
Awaiting Gate. Report findings in 繁體中文.
