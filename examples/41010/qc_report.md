# QC report: 41010

Source: `ndbc` · 6347 records · 2026-10-05 00:00 to 2026-11-19 02:10 UTC

## Flags per variable

| Variable | GOOD | SUSPECT | FAIL | MISSING | NOT_EVALUATED |
|---|---|---|---|---|---|
| WDIR | 6208 | 0 | 0 | 139 | 0 |
| WSPD | 6293 | 0 | 0 | 54 | 0 |
| GST | 6293 | 0 | 0 | 54 | 0 |
| WVHT | 3056 | 0 | 0 | 3291 | 0 |
| DPD | 0 | 0 | 0 | 4318 | 2029 |
| APD | 0 | 0 | 0 | 3296 | 3051 |
| MWD | 0 | 0 | 0 | 3296 | 3051 |
| PRES | 6295 | 0 | 0 | 52 | 0 |
| ATMP | 6264 | 0 | 0 | 83 | 0 |
| WTMP | 6000 | 11 | 0 | 336 | 0 |
| DEWP | 6264 | 0 | 0 | 83 | 0 |
| VIS | 0 | 0 | 0 | 6347 | 0 |
| PTDY | 0 | 0 | 0 | 5291 | 1056 |
| TIDE | 0 | 0 | 0 | 6347 | 0 |

## Events (2)

| Event | Worst flag | Tests | Points | LLM second opinion |
|---|---|---|---|---|
| WTMP@2026-11-02T01:20Z | SUSPECT | flat_line | 11 | not reviewed |
| *@2026-11-02T23:10Z | SUSPECT | gap | 1 | not reviewed |

_Flags come only from the deterministic tests. LLM opinions are advisory; a person decides._
