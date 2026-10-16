# API contract notes

Snapshot: 17 October 2026, https://api.arct.cloud/v1/openapi.json, API 1.0.0 / OpenAPI 3.1.0, 22 operations.

`upstream-openapi.json` is the unchanged semantic upstream contract. Run `python3 scripts/prepare_openapi.py` to produce `openapi.json`. The local overlay only assigns stable resource/action operation IDs and describes resize HTTP 202 with the documented `ResizeResponse`. It does not change backend behavior. Generators consume `openapi.json`.

Upstream follow-up before a stable release:

- Adopt stable operation IDs.
- Add the resize 202 body schema and verify it against the backend.
- Clarify that the `provisioning` list filter includes failed builds; `error` remains unsupported as a list filter until the backend changes.
- Resolve the label limit: schema says 100, prose says 10. Do not silently reduce the schema or claim the discrepancy is fixed.
- Update the introduction: scheduled deletion and cancellation are supported.

Generation is pinned to OpenAPI Generator 7.26.0 where used. Each package records its generator settings and any reproducible adaptations. Unknown response enums must remain usable; request enum validation must not be weakened.

