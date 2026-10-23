# API contract notes

Snapshot: 23 October 2026, https://api.arct.cloud/v1/openapi.json, API 1.0.0 / OpenAPI 3.1.0, 25 operations.

`upstream-openapi.json` is the unchanged semantic upstream contract. Run `python3 scripts/prepare_openapi.py` to produce `openapi.json`. The local overlay only assigns stable resource/action operation IDs and describes resize HTTP 202 with the documented `ResizeResponse`. It does not change backend behavior. Generators consume `openapi.json`.

Upstream follow-up before a stable release:

- Adopt stable operation IDs.
- Add the resize 202 body schema and verify it against the backend.
- Resolve the label limit: schema says 100, prose says 10. Do not silently reduce the schema or claim the discrepancy is fixed.

Datacenter codes identify placement (`ams2`); location codes remain supported (`ams`). Create requests accept either field and the server rejects missing placement or conflicting values. The upstream schema omits that cross-field rule; SDKs validate it without changing the snapshot. Requests keep their patterns and reject unknown fields; response fields tolerate unknown values and absent additions. `Server.datacenter` may also be null. `Location.datacenters` and `Plan.datacenters` list supported codes. The shared fixtures cover these additions and 49 error/status pairs, including `400 datacenter_unavailable` and `422 datacenter_mismatch`.

The live snapshot also adds credit transactions and invoice payment operations. They are retained in the generated contract; the datacenter feature does not add bespoke credit workflows. Fixtures include their documented error codes and `node_maintenance`.

The `provisioning` list filter includes failed builds; `error` remains unsupported as a list filter.

Generation is pinned to OpenAPI Generator 7.26.0 where used. Each package records its generator settings and any reproducible adaptations. Unknown response enums must remain usable; request enum validation must not be weakened.

