# Live validation — 17 October 2026

Tested implementation: `6e56b85`, API `https://api.arct.cloud/v1`.

All 72 checks passed against the real API using a user-supplied `read_write` token. The token was entered through hidden stdin and passed to child processes through their environment; it was not saved in repository files. Reports omit account identity, resource IDs, response bodies, and credentials.

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

Successful endpoint coverage: **13 of 22 operations** — all 11 GET operations and SSH-key creation/deletion. The first read pass had no existing SSH key to retrieve; the lifecycle tests subsequently covered that endpoint in every interface.

The remaining nine operations were not exercised live: server create, update, delete, start, stop, restart, reinstall, cancel deletion, and resize. No existing server was changed, and no paid server operation was requested. Provisioning, server wait transitions, resize payments, one-time server passwords, and live retry/rate-limit failures remain outside this validation. Their earlier mocked tests do not establish live backend behavior.

Execution was on macOS. This validation does not establish native Linux/Windows behavior or publication readiness, and does not resolve the remaining [upstream contract issues](../api/contract-notes.md).
