# Arct Cloud SDKs and CLI design

Status: accepted for implementation on 17 October 2026, amended by the user to use a Go CLI. Python and TypeScript/JavaScript are the SDK scope; no separate Rust SDK was selected.

Independent builder review completed against the administrator PDF: no important unanswered design questions. Contract corrections and generator compatibility remain implementation gates.

## Intent and decisions

Customers must be able to perform every public Arct Cloud API operation from an English CLI and integrate those operations into their applications through SDKs. Charges, destructive operations, and asynchronous provisioning must remain understandable and predictable.

User requirements: English commands/help/errors/docs; full public API coverage; incorporate all five areas of the administrator's Python SDK requirements. Source: [administrator PDF](/Users/tunc/Downloads/arct-cloud-python-sdk-5-musts.pdf), dated 16 October 2026.

Recommended implementation choices, not user-selected languages:

- Deliver a Go CLI using a shared Go API client, a Python SDK, and a TypeScript/JavaScript SDK in the same project. All cover the same 22 operations. Python is required by the PDF; TypeScript is the proposed second language.
- Python 3.11+, package `arct-cloud`, imports `Arct` and `AsyncArct` from `arct`. A standalone Go executable exposes `arct` and shares its Go API client. Names and registry ownership must be verified before release.
- Distribute the Go CLI as standalone macOS/Linux/Windows binaries. Use standard-library facilities unless a concrete CLI requirement justifies a dependency. The Python SDK remains a PyPI package.
- Generate models and endpoint transport from a pinned OpenAPI snapshot. Keep the small resource facade, retry/recovery policy, pagination, waiters, throttling, and CLI behavior outside generated files. Never patch generated output manually.
- Use one repository with separate `python/`, `go/`, and `typescript/` package directories, a shared API contract, and shared behavior fixtures. No custom SDK framework, plugin system, or runtime schema downloader.

## Provider evidence and what it changes

| Provider | Verified approach | Arct decision |
| --- | --- | --- |
| [DigitalOcean doctl](https://github.com/digitalocean/doctl) | Go CLI; its [module dependencies](https://github.com/digitalocean/doctl/blob/main/go.mod) include the godo SDK. [Commands](https://docs.digitalocean.com/reference/doctl/reference/compute/action/wait/) expose contexts, text/JSON output, and waiting. | Reuse the SDK; provide account contexts, machine-readable output, and bounded waiting. |
| [Hetzner hcloud](https://github.com/hetznercloud/cli) | Go CLI using [hcloud-go](https://github.com/hetznercloud/cli/blob/main/go.mod), with [binary/package installation and contexts](https://github.com/hetznercloud/cli/blob/main/docs/tutorials/setup-hcloud-cli.md). Its [Python SDK](https://github.com/hetznercloud/hcloud-python) exposes resource methods. | Use resource-oriented SDKs and CLI commands. The user selected Go for standalone CLI distribution; reuse the Go client beneath the CLI. |
| [Akamai/Linode CLI](https://github.com/linode/linode-cli) | Python CLI generated from OpenAPI, installed through PyPI; [output controls](https://github.com/linode/linode-cli/wiki/Output) include tables, JSON, selected fields, and header suppression. | Python distribution is a proven alternative. Keep endpoint coverage generated and presentation deliberately small. |

These are design references, not a requirement to reproduce each provider's feature set. Arct has no public action-ID endpoint, so waiters must use Arct's actual server and resize status endpoints.

## Contract baseline and corrections

Checked 17 October 2026: [live OpenAPI](https://api.arct.cloud/v1/openapi.json) and the [documentation copy](https://docs.arct.cloud/api-reference/openapi.json) match. OpenAPI 3.1.0, API version 1.0.0, base URL `https://api.arct.cloud/v1`, 22 operations. Operation IDs are unique and local schema references resolve.

Resolve these in the backend-owned contract before a stable SDK release:

1. Replace FastAPI-derived operation IDs with stable resource/action identifiers. Preserve the PDF's public surface, such as `servers.list` and `servers.start`; exact generator spelling is a build concern, not the public interface.
2. Declare `ResizeResponse` for the resize endpoint's `202` JSON body after confirming actual backend behavior. It currently has only a description.
3. Confirm the server status filter: returned statuses include `error`, while the filter excludes it and says `provisioning` includes failed builds. Either add `error` server-side or document that intentional distinction. Never send an unsupported filter just to make types symmetrical.
4. Resolve the label limit: `maxItems: 100` conflicts with the description's limit of 10. Preserve actual server semantics rather than guessing.
5. Correct the introduction's statement that scheduled deletion is dashboard-only. `DELETE ...?at_period_end=true` and `POST .../cancel-deletion` are present in the API.

Any temporary generation overlay must be explicit, reviewed, and linked to an upstream contract correction. It cannot invent backend functionality. The SDK workspace does not contain the backend, so these are integration dependencies, not completed changes.

## Requirement 1: reproducible generation

The PDF requires generated models and transport. Selecting a generator solely because it emits Python is insufficient: Pydantic, Decimal, sync/async, omitted fields, nullable unions, and unknown response enums must all work.

Start the implementation with a bounded generator compatibility check, after this design is accepted. The first local candidate is [OpenAPI Generator's Python generator](https://openapi-generator.tech/docs/generators/python/), whose documented options include HTTPX, synchronous variants, Decimal mapping, and hatchling. Verify a pinned released version against the real schema; current documentation alone is not proof. Generated sync adapters must work when invoked from a thread with an already-running event loop, or an alternative native sync transport must be selected.

The PDF's named alternatives remain possible: [Speakeasy](https://www.speakeasy.com/docs/sdks/languages/python/methodology-python) documents Pydantic and sync/async generation. A hosted generator requires an explicit account/cost decision if the local candidate cannot meet the requirements. Do not silently switch to non-Pydantic models or handwritten endpoint transport. Builder may select exact versions and small supported template customizations after the check; record the result before implementing the public facade.

CI regenerates deterministically from the checked-in contract. An upstream spec-change trigger, or a daily hash comparison when that integration is unavailable, opens an update PR with the contract and generated diff. No automatic merge. Shared fixtures and endpoint coverage checks must pass before updating packages.

## Requirement 2: Python API and waiters

Public resources: `account`, `servers`, `ssh_keys`, `locations`, `plans`, `images`, `invoices`.

```python
from arct import Arct

with Arct() as client:
    for server in client.servers.list():
        print(server.id, server.status)

    result = client.servers.create(
        hostname="web-1",
        location="fra",
        plan="vm.small",
        image_id=image_id,
        ssh_key_ids=[key_id],
    )
    server = client.servers.wait_until(result, "running")
```

- Explicit token overrides `ARCT_TOKEN`. Missing credentials fail locally. Clients are reusable context managers with explicit close/aclose support and finite HTTP timeouts.
- `Arct` has synchronous resource methods; `AsyncArct` has async methods and async iterators. Async retry, polling, and throttle waits never block the event loop.
- Every `.list()` is a lazy iterator across pages, requesting 100 items per page by default. Preserve filters between pages. Provide `.list_page(page=..., per_page=...)` for exact pagination and metadata. Empty lists stop immediately; page-number pagination is not a snapshot during concurrent changes.
- Pydantic models; monetary values use `Decimal`, parsed from the original JSON numeric tokens rather than through binary floats. Serialize accepted monetary request fields without losing precision. Preserve omitted vs explicit null vs empty collections; particularly omitted `ssh_key_ids` and `[]` have different behavior.
- Response enums accept unknown strings; input validation still follows the server's allowed values. New response fields must not break parsing.
- `wait_until(server_or_result, target_status, timeout=600)` polls every 5 seconds by default, with configurable 5-10 second cadence and a monotonic deadline. It returns the final server, reports terminal failures promptly, and includes the last observed state on timeout. Cancellation stops waiting, not the server operation.
- Create returns HTTP `201`, not `202` as one PDF sentence suggests. Preserve the complete order/server/password response. If `server` is null, use `order.server_id`; otherwise resolve a matching hostname by paginating. That fallback is discovery for an acknowledged creation, not proof that an unacknowledged request succeeded. Pre-orders may outlive the default deadline and must be reported explicitly.
- Start/stop/restart/reinstall return `202`. After restart/reinstall, do not interpret a stale initial `running` observation as proof of completion. Backend transition guarantees must be checked; until then, require observing a relevant transition and the target state, or time out with completion unverified. Do not invent action IDs.
- Resize waiting checks `resize-options.pending_resize` and verifies the requested final plan; `200 applied` and `202 pending_payment` are distinct. Do not start a server before the resize is applied. No hidden stop/start side effects in `resize()`.

## Requirement 3: charge-safe policy and typed errors

Follow [Arct error rules](https://docs.arct.cloud/api-reference/errors) and [operation semantics](https://docs.arct.cloud/api-reference/creating-servers). One policy owns retry decisions; disable independent retry layers in generated transports.

| Condition | Behavior |
| --- | --- |
| Any error with `details.order_intent_id`, or `409 payment_pending` | Raise `ChargeUnknownError`; preserve support identifiers. Never retry. This rule has priority over status-based retry. |
| `429` | Honor `Retry-After`; bound waiting by the operation deadline. Count every network attempt toward the retry limit. |
| GET network errors, `500`, `503` | Exponential backoff with jitter, maximum 3 total attempts. |
| Create network errors, `500`, `503`, without a charge-unknown marker | Retry the identical request and hostname under the documented hostname reservation behavior, maximum 3 total attempts. Do not describe this as a general idempotency-key protocol. |
| Create `409 promo_changed` | Resend the identical request once, within the same total-attempt budget. |
| Retried create returns `409 hostname_taken` | Reconcile using known order/server IDs when available. Otherwise list by hostname, compare creation time and requested attributes, and expose the candidate as an uncertain outcome; do not fabricate a successful order/password response. |
| Other mutation transport errors or `500` | Retry only after operation-specific safety is established. A lost resize, reinstall, or restart response is not permission to execute the action again. Reconcile observable state or report uncertainty. |
| Other `4xx` | Raise the typed error; no automatic retry. |

The PDF's hostname-plus-created_at shortcut cannot prove ownership of a concurrent create or recover a lost one-time password. The proposed safety amendment is explicit uncertainty when correlation is insufficient. Similarly, the PDF's network-error retry row must not be applied indiscriminately to all mutations. Tests must cover both refinements.

Exceptions: `AuthenticationError`, `PaymentRequiredError`, `PermissionDeniedError`, `NotFoundError`, `ConflictError`, `ValidationError`, `RateLimitError`, `APIError`, plus `ChargeUnknownError` and an uncertain-operation error. Preserve HTTP status, stable `.code`, safe `.details`, and validation `.fields`; unknown codes fall back by status. Non-JSON responses and network failures must also be usable errors. Error representations redact credentials and secrets.

`resize()` fetches the selected eligible option and submits its exact `amount_due_today` as `expected_amount` unless an explicit expected amount was supplied. The CLI displays the quote and passes that same amount after confirmation; it must not silently replace it with a newer quote. `price_changed` requires a new decision. A pending payment or hosted invoice URL is reported as such, not as completed resizing.

## Requirement 4: secrets, limits, compatibility

- Tokens are redacted from representations and diagnostics; default logs contain no request or response bodies. Never forward authorization to another origin during a redirect.
- Creation/reinstallation passwords are `SecretStr`, available through deliberate unwrapping. Default CLI output and JSON redact them. `--show-password` explicitly opts into returning the one-time value and is documented on create/reinstall. Preserve this value through `--wait`; polling must not overwrite the original response.
- Local CLI contexts hold named account credentials with owner-only access on supported operating systems. Support `ARCT_TOKEN` for ephemeral CI without persistence. Login validates an existing dashboard-created token; it does not create API tokens. Logout removes local credentials and does not revoke the token remotely.
- Implement client-side scheduling for reads 120/minute per token, writes 30/minute per token and account, and paid operations 5/minute plus 20/hour per token and account. Paid attempts also consume the write budget. Concurrent clients in the same process share account budgets after resolving the account ID; different tokens do not create extra account capacity.
- Local throttling is best effort across separate processes or machines; the server remains authoritative and `429` handling is mandatory. Do not introduce a distributed limiter service. CLI invocations must respect server feedback even when local history is unavailable.
- Recommend read-only tokens for read-only work. Explain `insufficient_scope` and `api_access_disabled` with actionable English messages.
- SDK 1.x targets API `/v1`. Publish a changelog, deprecate for at least one minor release, and remove public features only in a new major release. Document Python/runtime support separately from API compatibility.

## CLI coverage and behavior

Canonical grammar: `arct <resource> <action>`. IDs are UUIDs; location codes and plan slugs retain their API meaning. Full parity includes optional request fields, filters, and both deletion modes, not just one command per endpoint.

| API resource | CLI commands | Operations |
| --- | --- | ---: |
| Account | `account get` | 1 |
| Servers | `servers list`, `get`, `create`, `update`, `delete`, `start`, `stop`, `restart`, `reinstall`, `resize-options`, `resize`, `cancel-deletion` | 12 |
| Locations | `locations list` | 1 |
| Plans | `plans list` | 1 |
| Images | `images list` | 1 |
| SSH keys | `ssh-keys list`, `get`, `create`, `delete` | 4 |
| Invoices | `invoices list`, `get` | 2 |
| Local helpers | `auth login`, `logout`, `status`; `context list`, `use`, `delete`; `servers wait` | No extra API endpoints |

- Default output is readable tables/details. `--output json` returns a stable complete result, with documented secret redaction. `--columns` and `--no-header` apply to tables only. Progress, prompts, and diagnostics go to stderr; stdout contains only requested output.
- Default CLI listing retrieves one page, reflecting API defaults. `--page`, `--per-page`, and `--all` control retrieval explicitly. JSON for a page preserves the API envelope; `--all` emits an array. Do not silently load every server for ordinary listing.
- `--context` selects named credentials; explicit `ARCT_TOKEN` overrides stored credentials. The active credential source is visible through `auth status` without exposing it. Do not accept tokens in command-line flags.
- `--wait` applies to supported asynchronous commands; `--timeout` bounds waiting. A successful `202` without `--wait` means accepted, not finished. For `--wait` on create/reinstall, JSON retains the original response plus final observed state; it does not discard the password/order result. Immediate delete waits for `404` only after an acknowledged delete. Scheduled deletion reports `cancel_at` and rejects `--wait`.
- Confirmation is required for create/resize, destructive delete/reinstall, and billing-changing scheduled deletion/cancel-deletion. `--yes` explicitly bypasses prompts for automation. Noninteractive input without required confirmation fails before mutation. State commands remain directly scriptable. The SDK never prompts.
- Creation displays selected plan/location/billing period and the fact that a saved card is charged. There is no exact create-quote endpoint; never present a locally calculated price as guaranteed, especially with coupons, backups, or prepaid periods.
- Public-key file input reads a public key; explicit empty SSH-key and label arrays are representable. Boolean false is distinct from omission. Expose coupon, billing period, backups, reinstall hostname, delete protection, scheduled deletion, and resize amount controls.
- Stable exits: 0 success/accepted, 1 API or network failure, 2 usage/confirmation failure, 3 timeout or uncertain outcome, 130 interruption. JSON-mode failures emit a structured redacted error to stderr. Help and examples are English.

```bash
arct auth login --context production
arct servers list --output json --all
arct plans list --location fra
arct servers create --hostname web-1 --location fra --plan vm.small --image IMAGE_ID --ssh-key KEY_ID --wait
arct servers resize-options SERVER_ID
arct servers resize SERVER_ID --plan vm.medium --expected-amount 4.12 --yes
arct servers delete SERVER_ID --at-period-end --yes
arct servers cancel-deletion SERVER_ID --yes
```

Dashboard-only capabilities remain documented boundaries: token issuance/revocation, password resets, cards, invoice payment, backup/snapshot management, VNC, and crypto payments. Server creation can still enable backups. CLI does not add unsupported API operations.

## Requirement 5: tests and release

- Unit and mocked HTTP tests cover all 22 operations in sync and async, every documented error code, unknown codes/enums/fields, non-JSON failures, `204`, alternate success statuses, pagination, cancellation, and timeout behavior. Use pytest and respx when the chosen transport is HTTPX.
- Payment tests assert exact network attempt counts and identical create bodies; charge-unknown responses never retry; stale resize quotes do not silently update; ambiguous hostname recovery never claims success. Include lost responses and concurrent create candidates.
- Test Decimal parsing/serialization from raw JSON, omitted/null/empty distinctions, passwords across wait completion, secret-free repr/logging, account-shared throttling, rate-limit backoff, and async nonblocking waits.
- CLI tests assert 22-operation coverage, all optional fields, contexts, stdout/stderr separation, stable exits, no prompts in automation, confirmation before mutations, JSON output, and no accidental secrets. Test Python wheel installation and Go CLI builds on Linux, macOS, and Windows.
- Live CI uses a read-only token and GET endpoints only. Mutations, payments, deletes, and reinstalls are tested against mocks in CI. Any later live write smoke test is separately scoped to a disposable account and explicit spending limits.
- Build with `pyproject.toml` and hatchling, include `py.typed`, and publish versioned releases with [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) and [attestations](https://docs.pypi.org/attestations/). Start with a prerelease; publish 1.0.0 after contract and acceptance gates pass. Version package tags independently in the shared repository.
- Verify package names and organization ownership before the first actual publication. The PDF's historical availability claim is not a reservation; publishing placeholder packages is not part of planning.
- README quickstart covers token, SSH key, image selection, create, wait, and the native SSH command; include sync and async examples, retry/uncertainty rules, billing effects, and API boundaries.

## Delivery sequence and completion gates

1. Contract corrections and generator check: settle the five contract issues, choose and pin the generator, and demonstrate all required type/transport behaviors. Backend access is an implementation dependency, not needed to review this design.
2. Python SDK: implement generated core and small public facade, then verify all 22 operations and all five PDF requirements with mocks and read-only contract checks.
3. Go CLI: reuse its shared Go client, implement complete command/field coverage, and pass output, secrets, automation, installation, and payment confirmation tests.
4. TypeScript/JavaScript SDK: generate from the same contract; provide resource methods, async iteration, AbortSignal, typed errors, and the same retry/wait semantics. Use `typescript-fetch` as the initial generator candidate. Keep monetary wire types explicit and avoid client-side billing arithmetic; Python-specific Pydantic/SecretStr requirements remain Python-specific. Run shared behavior fixtures. Package name is provisional pending npm ownership checks.
5. Release: reviewed contract/generated diffs, passing package tests, English documentation, changelog, verified publisher identities, prerelease installation smoke tests, then stable publication.

No implementation time estimate is asserted before the generator check. Remaining builder choices are exact tool versions, package internals, table formatting, HTTP timeout defaults, and fixture organization. Material changes to delivery language, supported behavior, or hosted generator cost return to the owner; routine implementation details do not.
