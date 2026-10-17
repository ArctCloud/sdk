# Arct Cloud Python SDK

Python 3.11+. First preview: `0.1.0rc1`, targeting the Arct Cloud API `/v1`.

PyPI publication is pending account setup. To use the preview now, clone [ArctCloud/sdk](https://github.com/ArctCloud/sdk) and run `python3 -m pip install ./python` from its root. After registry publication:

```sh
python3 -m pip install "arct-cloud==0.1.0rc1"
```

Source and issues: [ArctCloud/sdk](https://github.com/ArctCloud/sdk).

Set `ARCT_TOKEN` to a dashboard-created API token. Prefer a read token for read-only work; mutations require `read_write`. An explicit `token=` overrides the environment. Missing credentials fail before a request.

```python
from arct import Arct

with Arct() as client:
    account = client.account.get()
    print(account.id)
    for server in client.servers.list():
        print(server.hostname, server.status)
```

Creating or resizing a server can charge the saved card. Backups, coupons, and billing period affect the charge; no create quote endpoint exists. SDK methods never prompt.

```python
import asyncio
from arct import AsyncArct

async def main():
    async with AsyncArct() as client:
        async for server in client.servers.list(location="fra"):
            print(server.id, server.status)
        page = await client.images.list_page(location="fra", page=1, per_page=20)
        print(page.pagination.total)

asyncio.run(main())
```

The native synchronous HTTPX client also works in a thread with an active event loop. Async retry, polling, and throttle waits use cancellable asynchronous sleeps. Close clients with context managers, `close()`, or `await aclose()`.

## Resources

- `account.get()`
- `servers.list()`, `list_page()`, `get(id)`, `create(...)`, `update(id, ...)`, `delete(id, at_period_end=...)`, `start(id)`, `stop(id)`, `restart(id)`, `reinstall(id, ...)`, `cancel_deletion(id)`, `resize_options(id)`, `resize(id, ...)`
- `ssh_keys.list()`, `list_page()`, `get(id)`, `create(name=..., public_key=...)`, `delete(id)`
- `locations.list()`, `plans.list(location=...)`, `images.list(location=...)`, and their `list_page()` methods
- `invoices.list()`, `list_page()`, `get(id)`

Each `list()` is lazy and fetches 100 items per page. `list_page()` preserves the typed API envelope and API defaults. Empty pages stop iteration. Page numbers do not represent a snapshot during concurrent changes. All request fields are available as keyword arguments and validated locally. Unsupported server status filters, including `error`, fail locally. The backend currently documents a conflicting label limit (10 in prose, 100 in schema); the SDK follows the schema and the backend remains authoritative.

Response models are Pydantic models, available from `arct.models`; new fields and response enum values are accepted. All monetary response values are `Decimal`, decoded from original JSON numeric tokens. Optional input fields are omitted unless passed; explicit nullable `None`, `[]`, and `False` retain their distinct meanings. In particular, omitted `ssh_key_ids` selects saved keys, while `[]` requests a password where supported.

## Retries and uncertainty

GET network failures and HTTP 500/503 retry with exponential jitter. Creation uses the documented hostname reservation behavior and retries the identical body; this is not a general idempotency protocol. HTTP 409 `promo_changed` resends once. HTTP 429 respects `Retry-After`. Every call permits at most three total attempts, with a default 600-second operation deadline.

Any `details.order_intent_id` or HTTP 409 `payment_pending` raises `ChargeUnknownError` immediately, even if the HTTP status would otherwise retry. Preserve its support identifiers and inspect billing before another purchase. Other mutation network/500/503 failures raise `UncertainOperationError`; repeating restart, reinstall, delete, or resize automatically could apply the action twice.

A retried create that encounters `hostname_taken` raises `UncertainOperationError` with `.candidates`. A matching hostname and timestamp cannot establish order ownership or recover a one-time password. The SDK never constructs a successful order from such a candidate. Known server IDs are queried directly when supplied by the API.

Exceptions exported from `arct`: `AuthenticationError`, `PaymentRequiredError`, `PermissionDeniedError`, `NotFoundError`, `ConflictError`, `ValidationError`, `RateLimitError`, `APIError`, `ChargeUnknownError`, `UncertainOperationError`, `OperationFailedError`, and `WaitTimeoutError`. They expose `.status`, `.code`, safe `.details`; validation errors expose `.fields`. Unknown codes use the status class. `insufficient_scope` directs callers to a `read_write` token; `api_access_disabled` directs callers to the dashboard.

`servers.resize(id, plan="vm.medium")` reads eligible resize options and sends the exact `amount_due_today` quote as `expected_amount`. Supplying an explicit amount retains that value and never silently replaces a stale quote. A `price_changed` conflict requires a new decision. Decimal amounts use the contract's string wire alternative to preserve every digit. **Explicit `expected_amount=None` deliberately opts out of price protection and accepts the current API price.** HTTP 200 `applied` and HTTP 202 `pending_payment` remain distinct. Resize never stops or starts a server.

## Waiting and passwords

`servers.wait_until(id_or_server_or_create_result, "running", timeout=600, poll_interval=5)` uses a monotonic deadline; polling intervals may be 5–10 seconds. It resolves acknowledged delayed creates from `order.server_id`, then by the original hostname. Pre-orders can exceed the default deadline. Timeouts expose `.last_state` and do not cancel remote operations.

Pass the original restart/reinstall response (or its server object) to preserve transition tracking. A stale initial `running` observation alone cannot verify restart/reinstall completion. If no transition is observed, the waiter times out as unverified. A bare ID has no action history and waits only for the requested current status.

`servers.wait_resize(id, resize_result)` checks that `pending_resize` clears and verifies the requested plan in both options and the server response. Pending payment may require dashboard action. Waiting never starts the server.

Create/reinstall passwords are `SecretStr`. Read them deliberately with `result.password.get_secret_value()` when non-null. Default representations and JSON serialization mask them. Keep the original result: waiters return a final server without overwriting the original order/password. Delayed builds and pre-orders may return null passwords and send credentials by email.

## Transport and limits

`Arct(base_url=..., transport=..., timeout=30, operation_timeout=600)` and `AsyncArct` accept HTTPX transports for tests. HTTP timeouts and deadlines must be finite and positive. Synchronous calls check deadlines between raw response chunks and before accepting success; an in-progress blocking socket phase may overrun the operation deadline until its underlying HTTP timeout, while asynchronous calls cancel in-flight I/O. HTTPS is required except explicit localhost test URLs. Redirects are not followed, so authorization cannot move to another origin. SDK logging never records bodies.

Clients resolve `account.get()` before the first mutation to share account budgets. Local rolling limits are 120 reads/minute per token, 30 writes/minute per token and account, and 5 paid calls/minute plus 20/hour per token and account. Paid calls also consume writes. Sync and async clients share budgets within the process; separate processes and machines rely on server enforcement. Server `429` feedback remains authoritative.

Dashboard-only capabilities include token issuance/revocation, password resets, card management, invoice payment, backup/snapshot management, VNC, and crypto payments. Creation can enable backups, but this SDK adds no unsupported endpoints.

## Development

From the repository root with Python 3.11+ and Java 17+:

```sh
python -m pip install './python[test]'
python python/scripts/generate.py
python python/scripts/generate.py --check
python -m pytest python/tests
python -m build python
```

Generation uses checksum-pinned OpenAPI Generator 7.26.0, the checked-in normalized schema, two small Mustache templates, and deterministic schema annotations. Generated endpoint bindings construct methods, paths, queries, request models, and typed responses. The shared HTTPX policy transport owns retries, deadlines, and throttling. Do not edit `_generated/` manually. See `GENERATION.md` for compatibility evidence.

Release publication uses trusted publishing and attestations through repository CI. No package publication or live mutation occurs during tests. Public features are deprecated for at least one minor version before removal in a major release; API and Python runtime compatibility are documented separately.
