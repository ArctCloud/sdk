# Arct SDKs and Go CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Each package task has independent ownership; the user authorized subagents and execution.

**Goal:** Deliver a usable Go CLI and Python/TypeScript SDKs covering all 22 public API operations with the administrator's Python requirements.

**Architecture:** A pinned OpenAPI snapshot generates endpoint bindings and models. Package-specific handwritten policy layers implement safe retries, pagination, waiting and secrets. The Go CLI reuses its Go client; Python and TypeScript are independently installable packages.

**Tech Stack:** Go, Python 3.11+/HTTPX/Pydantic, TypeScript/native fetch, pinned OpenAPI generation, standard package build tools.

**Spec:** `docs/superpowers/specs/2026-10-17-sdk-cli-design.md` with the user's accepted Go CLI amendment.

## Global Constraints

- English code, docs, errors, help, reports, and comments. Comments at most 2-3 words; prefer none.
- Python package `arct-cloud`, import `arct`, `Arct` and `AsyncArct`; TypeScript package `@arct-cloud/sdk`; all initial versions 0.1.0. Names provisional until actual publication.
- One Go CLI named `arct`, standalone macOS/Linux/Windows builds. No Python CLI and no Rust SDK in this accepted scope.
- Resource methods expose all 22 endpoints and every request field; generated code is reproducible.
- `ARCT_TOKEN`, production URL `https://api.arct.cloud/v1`; custom base URL and transport injection for testing. HTTPS required except explicit localhost test servers.
- No token/secret leakage, no cross-origin redirects with authorization, no API writes or purchases during development/CI.
- Error precedence: `order_intent_id` / `payment_pending` never retry; maximum three total attempts; identical create body; no blind other mutation retry.
- Poll 5 seconds, default deadline 600 seconds; preserve create/reinstall original results and secrets through waiting.
- Work only in your assigned files; do not revert other agents. No worker commits; the orchestrator handles integration commits sequentially.
- The backend is absent. Use only the documented overlay in `api/contract-notes.md`; retain outstanding backend issues honestly.

## Review Focus

- Ambiguous writes, duplicated hostnames and concurrent creation must never produce fabricated successful orders.
- Omitted/null/empty request fields and new response enum values must survive generation correctly.
- Retry and throttle waits must respect cancellation and deadlines, including async Python and AbortSignal.
- CLI flags, stdin, prompts and JSON output must not cause secret exposure or mutations before confirmation.
- Generation, built-package installation and the full operation matrix must be checked, not only helper functions.

### Task 1: Shared contract and repository integration

**Owner:** orchestrator. **Files:** `api/`, `scripts/prepare_openapi.py`, root documentation/build files, `.github/workflows/`.

**Interfaces:** `api/openapi.json` provides `operationId` values `<resource>_<action>` and `x-arct-resource` / `x-arct-action`. Package folders are `python/`, `typescript/`, `go/`. Workers own their package's generation scripts.

- [ ] Snapshot upstream, normalize deterministically, check 22 unique operations and resolved refs.
- [ ] Write shared `api/test-cases.json` with representative error envelopes and edge-case values for package tests.
- [ ] Add root commands to generate/check/build/test each package, plus English quickstart and contract limitations.
- [ ] Configure CI package checks, read-only optional live tests, spec-drift PR creation and release workflows; do not publish now.
- [ ] Verify all package artifacts install/run, commit only verified project files.

### Task 2: Python SDK

**Owner:** Python worker. **Files:** `python/` exclusively; report in `.superpowers/sdd/arct-sdk/python-report.md`.

**Interfaces:** `from arct import Arct, AsyncArct`; resources `account`, `servers`, `ssh_keys`, `locations`, `plans`, `images`, `invoices`. `.list()` returns lazy iterators; `.list_page()` returns a typed page. `servers.wait_until(value, target_status, timeout=600)` accepts ID/server/create-result. Parameters may be keyword fields, not raw URLs.

- [ ] Read the design and PDF (`pdftotext` available); run a bounded OpenAPI Generator 7.26.0 compatibility check with native sync/async HTTPX and Pydantic/Decimal. Record evidence and adaptations. Use supported templates/adaptations, never edit generated output by hand; consult orchestrator if the standard generator proves unsuitable.
- [ ] Write failing tests for all 22 wire operations, omitted/null/empty, Decimal raw JSON, password masking, unknown enum/fields and both sync/async clients.
- [ ] Implement generated models/bindings and minimal policy facade, lazy pagination, close/aclose, finite HTTP timeouts, typed errors, account-aware throttling and safe retries.
- [ ] Write failing tests for exact retry counts, charge-unknown priority, ambiguous create reconciliation, quote preservation, async cancellation and waiter deadlines. Implement those rules including create server:null discovery and resize waiting.
- [ ] Run full pytest suite and deterministic regeneration check. Build wheel/sdist and smoke-test the wheel in a fresh environment.
- [ ] Write package README with sync/async quickstarts, retry behavior, one-time passwords, API boundaries and Python 3.11+ support. Report actual checks and remaining concerns.

### Task 3: Go client and CLI

**Owner:** Go worker. **Files:** `go/` exclusively; report in `.superpowers/sdd/arct-sdk/go-report.md`.

**Interfaces:** Go module `arct.cloud/sdk/go` (local module path; vanity hosting not yet configured). `go/cmd/arct` builds CLI; internal/shared client handles all wire calls. CLI grammar and behavior follow the design's CLI section; use the Go language instead of its obsolete Python packaging statements.

- [ ] Write failing Go HTTP tests for operation coverage and policy before implementation. Generate endpoint/model bindings using a pinned standard generator compatible with the 3.1 schema; explicit reproducible compatibility conversion is allowed.
- [ ] Implement client with all endpoints, context cancellation, finite timeouts, error details, redaction, pagination, retry safety, quoted resize and waiters. Reuse this client from CLI, no duplicate HTTP stack.
- [ ] Write CLI tests for every resource action and all optional fields; confirmations before mutations; table/JSON, one-page/all-page behavior, stderr separation, exit codes, context persistence and masking.
- [ ] Implement `auth login/logout/status`, `context list/use/delete`, full resource command groups, `servers wait`, `--wait`, `--timeout`, `--yes`, `--show-password`, `--output`, `--columns`, `--no-header`, `--all`, `--page`, `--per-page`.
- [ ] Test unknown flags, missing identifiers, false vs unset booleans, empty SSH keys and labels, invalid resize amounts, server:null, pending payment, stale running state and cancellation. Preserve original response through wait.
- [ ] Run `go test -race ./...`, `go vet ./...`, build/run help and cross-compile Linux/macOS/Windows amd64/arm64 with CGO disabled where supported. Document any platform limitation honestly.
- [ ] Write Go README with local builds and CLI examples; no claim of a configured public Go vanity module or published binaries.

### Task 4: TypeScript/JavaScript SDK

**Owner:** TypeScript worker. **Files:** `typescript/` exclusively; report in `.superpowers/sdd/arct-sdk/typescript-report.md`.

**Interfaces:** `import { Arct } from '@arct-cloud/sdk'`; resource names camelCase (`sshKeys`), methods camelCase (`listPage`, `waitUntil`, `resizeOptions`, `cancelDeletion`). Native fetch; node>=22; `.list()` async iterable, `.listPage()` typed page, AbortSignal supported across request/retry/wait.

- [ ] Generate typed models and endpoint bindings from the normalized schema, starting with pinned OpenAPI Generator typescript-fetch. Keep generated output and public facade distinct and reproducible; preserve unknown response fields/enums.
- [ ] Write failing node tests for all 22 operations, query serialization, explicit false/empty vs omitted fields, unknown enum values, 204, JSON/non-JSON errors, token handling and path encoding.
- [ ] Implement minimal resource facade with reusable fetch transport, bounded safe retries, typed errors, pagination, cancellation, masking, quoted resize, server discovery and waiters. Do not perform billing arithmetic locally.
- [ ] Test ambiguous writes, charge-unknown precedence, retry counts, Retry-After and aborted sleep, deferred server discovery, pre-orders, resize status, no stale-running false success and secret masking.
- [ ] Run full build/typecheck/test suite and generation check, pack the npm package and smoke-test importing built artifacts from a clean temporary consumer.
- [ ] Write README and examples, record supported runtimes and no browser-side secret token usage. Report actual checks.

### Task 5: Independent review and final acceptance

**Owner:** orchestrator with fresh GPT-6.1 xhigh reviewers.

- [ ] Review each package against the design, test evidence, schema and PDF; return concrete defects to its original worker.
- [ ] Run all full suites after fixes, regeneration checks, package installs and native CLI smoke tests.
- [ ] Perform one whole-project review covering semantic parity, CLI safety, generation and CI packaging.
- [ ] Resolve material findings, record actual validation and limitations, and commit the finished implementation. Do not publish registry packages or contact the API with mutation requests.
