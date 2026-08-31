# empire-operators

Fleet-installable extract of `empire_os`'s **general** (non-talora)
reasoning operators, plus ASGI middleware built on them.

Each operator is a pure `execute(state: dict) -> dict` transform — no I/O,
no runtime dependencies. Bodies are copied verbatim from
`empire_os/operators/all_operators.py` and kept in sync by convention;
this package is the installable subset the OS42 engine fleet depends on
(the ~41 talora / content-brand operators stay in `empire_os`).

Sibling-package install, same pattern as `autonomy-events` / `unkey-auth`:

```
# in an engine's requirements.txt
-e ../empire-operators
```

## What's here (v0.1.0 — Step 8 Phase B first slice)

| export | use |
|--------|-----|
| `SafetyBoundaryOperator` | scan text for prompt-injection / `drop table` / `<script` patterns |
| `ConstraintEnforcer` | output length / forbidden-words checks |
| `ValidationOperator` | required-fields check on a dict output |
| `ErrorRecoveryOperator` | classify an error → retry/abort with a ceiling |
| `SafetyBoundaryMiddleware` | ASGI middleware: 400s any POST/PUT/PATCH body matching an unsafe pattern |

## Middleware

```python
from empire_operators.middleware import SafetyBoundaryMiddleware
app.add_middleware(SafetyBoundaryMiddleware, exempt_paths=["/health"])
```

- Only `POST` / `PUT` / `PATCH` with a body are scanned.
- `multipart/form-data` (file uploads) is skipped.
- Bodies over `max_scan_bytes` (default 256 KiB) pass through unscanned.
- Buffers the body once and replays it downstream unchanged.

## Roadmap

The remaining ~40 general operators (`InputInterpreter`, `DriftMonitor`,
`AuditCycleOperator`, `AccessControlOperator`, `LifecycleOperator`,
`PriorityResolver`, …) land here incrementally as they get real fleet
consumers. See `empire_os/EMPIRE_OS_INTEGRATION_ANALYSIS.md`.
