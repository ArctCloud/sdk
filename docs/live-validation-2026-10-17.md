# Live validation — 17 October 2026

Tested implementation: `6e56b85`, API `https://api.arct.cloud/v1`.

All 72 initial checks passed against the real API using a user-supplied `read_write` token. The token was entered through hidden stdin and passed to child processes through their environment; it was not saved in repository files. Reports omit account identity, resource IDs, response bodies, and credentials. A subsequent zero-cost VPS purchase and scheduled cancellation also passed, as described below.

| Interface | Read checks | SSH-key lifecycle checks | Result |
| --- | ---: | ---: | --- |
| Python synchronous SDK | 12 | 4 | Pass |
| Python asynchronous SDK | 12 | 4 | Pass |
| Go CLI | 12 | 4 | Pass |
| TypeScript SDK, Node 22.12.0 | 12 | 4 | Pass |
| Direct HTTP baseline | 7 | — | Pass |
| Final cleanup verification | 1 | — | Pass |

Read checks covered account access, all six list resources, existing server and invoice details, server resize options, pagination, and a real nonexistent-server 404. Python also verified monetary server values deserialize as `Decimal`. CLI responses were parsed as JSON; its 404 exit status and structured stderr were checked. Account identity matched across interfaces.

Each interface created one uniquely named temporary Ed25519 SSH key, retrieved it, deleted it, and verified a subsequent GET returned 404. The four temporary keys were removed. The final API list confirmed zero SSH keys, matching the initial state. Temporary local private keys were removed before their public keys were submitted.

Successful endpoint coverage: **15 of 22 operations** — all 11 GET operations, SSH-key creation/deletion, server creation, and server deletion scheduled at period end. The first read pass had no existing SSH key to retrieve; the lifecycle tests subsequently covered that endpoint in every interface.

Server creation was subsequently attempted once through the Python SDK using London `cvm.pico`, Ubuntu 24.04, yearly billing, backups disabled, and the user-supplied 100% coupon. The API returned HTTP 402 `no_payment_method`, correctly surfaced as `PaymentRequiredError`. No retry or coupon-free fallback was sent. A subsequent read confirmed no matching server and no invoices created since the attempt; totals remained 12 servers and 46 invoices. The API contract states this error charges nothing. That attempt was blocked by the API's saved-payment-method requirement; its response did not establish whether the coupon would otherwise be accepted.

The user subsequently authorized saving a supplied card through the dashboard; the saved-card list confirmed success. The dashboard accepted the coupon for the same yearly configuration and displayed $0.00 due today, with renewal at $32.68/year. The user approved creation with cancellation at period end. Card details were not written to repository files.

One new creation request returned HTTP 201 with order amount $0.00 USD and payment method `promo`. The Python SDK observed provisioning complete through `wait_until(..., 'running')`. It then scheduled deletion with `at_period_end=true`; a fresh GET confirmed the server remained running and `cancel_at` was 17 October 2027 at 00:00 UTC. The Go CLI independently confirmed the server, annual billing, running status, and scheduled cancellation. TCP port 22 returned an OpenSSH Ubuntu banner; SSH authentication was not attempted. The one-time password was present and saved outside the repository in an owner-only file (mode 0600).

The remaining seven operations were not exercised live: server update, start, stop, restart, reinstall, cancel deletion, and resize. No pre-existing server was changed. Immediate deletion, other server action transitions, resize payments, SSH authentication, and live retry/rate-limit failures remain outside this validation. Their earlier mocked tests do not establish live backend behavior.

Execution was on macOS. This validation does not establish native Linux/Windows behavior or publication readiness, and does not resolve the remaining [upstream contract issues](../api/contract-notes.md).
