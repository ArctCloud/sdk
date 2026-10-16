# Generation compatibility

Generator: OpenAPI Generator 7.26.0. Root `scripts/openapi_generator.py` downloads and checks its pinned SHA256. Input: `api/openapi.json`; local contract overlay and unresolved backend items are recorded in `api/contract-notes.md`.

The bounded stock `python` / `httpx` check used `supportHttpxSync=true`, `mapNumberTo=Decimal`, and `disallowAdditionalPropertiesIfNotPresent=false` on the real schema. Evidence from its generated files:

- Sync operations call `sync_helper.run_sync()` to submit an async coroutine to a background event loop. This is not native synchronous HTTPX.
- `ApiClient.deserialize()` calls plain `json.loads()` before Decimal conversion, rounding original monetary tokens through floats.
- Response enum models and field validators reject new response strings.
- Optional nonnullable request fields become `Optional[...]` and accept explicit null; `to_dict()` also emits defaults that were omitted.
- Password fields use plain strings.

The approved adaptation is `templates/model.mustache` and `templates/api.mustache`, with minimal annotations in `scripts/generate.py`. These generate strict Pydantic requests, forward-compatible Pydantic responses, SecretStr passwords, complete sync/async HTTPX endpoint bindings and native method signatures. API tag grouping is normalized only for generation so catalog resources have separate Python surfaces. The annotated temporary schema is never substituted for the shared contract.

The generated bindings delegate one generic policy transport to native `httpx.Client` / `httpx.AsyncClient`; this is where raw-token Decimal JSON decoding, exact Decimal request strings, retries, shared throttling, and bounded waits belong. There is no handwritten endpoint inventory and no hand-edited generated output. Account discovery and create reconciliation call generated bindings as well.

Run `python python/scripts/generate.py --check` from the repository root. It regenerates into a temporary directory and compares all generated Python bytes. The generator intentionally handles the checked-in schema forms rather than exposing a generic generator framework. New schema forms must be reviewed alongside generated diffs and tests.
