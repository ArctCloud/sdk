# @arct-cloud/sdk

Arct Cloud API `/v1` client for Node.js 22 and newer. ESM JavaScript and TypeScript declarations; native fetch; no runtime dependencies. Version 0.1.0 is an initial preview. The npm name is provisional until publication.

```sh
npm install @arct-cloud/sdk
export ARCT_TOKEN=your_dashboard_token
```

```js
import { Arct, ChargeUnknownError, UncertainOperationError } from '@arct-cloud/sdk';

const arct = new Arct();
for await (const server of arct.servers.list({ location: 'fra' })) {
  console.log(server.id, server.status);
}
const page = await arct.servers.listPage({ page: 1, perPage: 20 });
console.log(page.pagination);
```

Use tokens only in trusted server processes. Never put a token in browser code. Prefer read-only tokens for reads. Explicit `token` takes precedence over `ARCT_TOKEN`; empty tokens fail locally. Tokens come from the dashboard; this package does not issue or revoke them.

## Resources

| Resource | Methods |
| --- | --- |
| `account` | `get` |
| `servers` | `list`, `listPage`, `get`, `create`, `update`, `delete`, `start`, `stop`, `restart`, `reinstall`, `resizeOptions`, `resize`, `cancelDeletion`, `waitUntil` |
| `sshKeys` | `list`, `listPage`, `get`, `create`, `delete` |
| `locations`, `plans`, `images` | `list`, `listPage` |
| `invoices` | `list`, `listPage`, `get` |

Body fields use their API names, for example `image_id`, `ssh_key_ids`, `enable_backups`, `billing_period`, `coupon_code`, `delete_protection`, `labels`, `public_key` and `expected_amount`. All request fields are represented in the generated types. Query fields use `perPage` and `atPeriodEnd`; other filter names match the API. Omitted, explicit `false`, empty arrays and nullable fields retain their meaning. Omitted SSH keys use saved keys; `ssh_key_ids: []` explicitly requests password access where supported.

All list resources have a lazy async iterable, requesting 100 items per page by default. `listPage()` retains the API's default page size unless specified and returns the full pagination envelope. Filters persist between pages; empty pages stop iteration. Concurrent API changes can affect page-number pagination.

```js
const arct = new Arct({ token: process.env.ARCT_TOKEN, timeoutMs: 30_000 });
const controller = new AbortController();
const result = await arct.servers.create({
  hostname: 'web-1', location: 'fra', plan: 'vm.small', image_id: 'IMAGE_UUID',
  ssh_key_ids: [], enable_backups: false, billing_period: 'monthly',
}, { signal: controller.signal });
const server = await arct.servers.waitUntil(result, 'running', {
  signal: controller.signal, timeoutMs: 600_000,
});
console.log(server.id);
console.log(result.password?.getSecretValue());
```

This creation example charges the saved card when executed. The SDK never prompts. Creation returns the original order/server result; creation and reinstall passwords are `Secret` objects. JSON serialization, string conversion and Node inspection redact their value. Only `getSecretValue()` reveals it. Waiting returns the observed server while the original result still holds its password. Store the original result if you need it later.

For SSH-key access, select a saved public key matching your local private key and a compatible image before creation:

```js
const location = 'fra';
const plan = 'vm.small';
const images = await Array.fromAsync(arct.images.list({ location }));
const image = images.find(image => image.name.toLowerCase().includes('ubuntu') &&
  (image.allowed_plans.length === 0 || image.allowed_plans.includes(plan)));
const keys = await Array.fromAsync(arct.sshKeys.list());
const key = keys.find(key => key.name === 'my-laptop');
if (!image || !key) throw new Error('Select a compatible image and save your laptop public key in Arct first.');
const created = await arct.servers.create({ hostname: 'web-ssh', location, plan,
  image_id: image.id, ssh_key_ids: [key.id] });
const ready = await arct.servers.waitUntil(created, 'running');
if (!ready.ipv4 || !ready.login_user) throw new Error('SSH connection details are unavailable.');
console.log(`ssh -i ~/.ssh/id_ed25519 ${ready.login_user}@${ready.ipv4}`);
```

Run the printed native SSH command with the private key matching the selected saved public key. This example charges the saved card when executed.

## Requests and waiting

Every network method accepts a final `{ signal, timeoutMs }` argument. For list iteration it is the second argument, and for server deletion it is the third (`delete(id, { atPeriodEnd: true }, requestOptions)`). Requests have a finite 30-second total retry deadline by default, including complete body consumption with injected transports. Creation recovery and resize quoting share the same operation deadline. Abort signals interrupt requests, local throttling, retries and polling. Cancellation stops waiting; an accepted server operation can continue remotely.

`waitUntil(resultOrId, status, options)` defaults to 600 seconds and a 5-second interval; `pollIntervalMs` supports 5000–10000. It reports terminal states promptly and throws `WaitTimeoutError` with `lastState`. Pre-orders can outlive the deadline. A delayed acknowledged creation uses `order.server_id`, then hostname discovery; when resuming a serialized result, supply `{ hostname: 'web-1' }` if its order has no server ID.

Pass the original restart/reinstall result into the waiter. These waits require an observed transition before accepting `running`; a stale initial running response cannot prove completion. Transition guarantees await backend verification. An unobserved transition times out with completion unverified. To wait for a resize, supply `{ plan: 'vm.medium' }`; the waiter checks `pending_resize`, the current plan, the server plan and target state. It never starts or stops a server automatically.

## Billing and errors

`resize(id, { plan })` fetches the selected eligible option and sends its original numeric `amount_due_today` text as `expected_amount`. No billing arithmetic occurs locally. An explicit number or decimal string is sent unchanged; decimal strings avoid JavaScript rounding. Explicit `expected_amount: null` preserves the API's **unguarded opt-out**, accepting the current backend price. `price_changed` is raised without re-quoting or retrying. `applied` and `pending_payment` remain distinct response statuses; hosted invoice/payment details remain available as returned by the API.

```js
try {
  await arct.servers.resize('SERVER_UUID', { plan: 'vm.medium', expected_amount: '4.12' });
} catch (error) {
  if (error instanceof ChargeUnknownError || error instanceof UncertainOperationError) {
    console.error(error.code, error.details);
  } else {
    throw error;
  }
}
```

Malformed successful envelopes and interrupted mutation bodies raise uncertainty with the received HTTP status. Response body failures never cause an automatic mutation resend. Errors expose `status`, `code`, redacted `details`, and validation `fields`. Available classes: `APIError`, `AuthenticationError`, `PaymentRequiredError`, `PermissionDeniedError`, `NotFoundError`, `ConflictError`, `ValidationError`, `RateLimitError`, `ChargeUnknownError`, `UncertainOperationError`, `WaitTimeoutError`, `OperationFailedError`. Permission failures explain `insufficient_scope` and `api_access_disabled`. Redirects are rejected; authorization is never forwarded to a redirect destination. Diagnostics do not include request or response bodies.

Reads and server creation retry network errors, HTTP 500 and 503, with jitter and at most three total attempts. Creation retries use the identical body and hostname, relying only on the documented hostname reservation behavior. `promo_changed` allows one resend within that budget. HTTP 429 respects numeric or date `Retry-After` within the deadline. `order_intent_id` on any error and HTTP 409 `payment_pending` take precedence: no retry. Other mutation network/500/503 failures raise uncertainty without repeating the mutation. A retried creation followed by `hostname_taken` raises uncertainty with any candidate servers and match/time indicators; candidates never fabricate an order or recover a lost one-time password.

Local scheduling enforces 120 reads/minute, 30 writes/minute, and 5 paid attempts/minute plus 20/hour. Paid attempts also consume the write budget. Limits are shared by token in this process. Before the first mutation, the SDK lazily reads `account.get()` to associate each token with its account budget. Concurrent first mutations with the same token share that lookup, with independent cancellation; the lookup is canceled when no live callers remain. The lookup consumes the normal read budget and inherits the mutation deadline and cancellation; an unsuccessful lookup prevents mutation. Separate processes/machines still rely on server rate limits.

JSON monetary response fields are JavaScript numbers and can lose precision for very large/high-precision amounts. Automatic resize quoting separately preserves the original numeric source text before rounding. Use explicit decimal strings for accepted monetary request fields. Response dates stay ISO strings; unknown response fields and enum strings survive parsing. Unsupported request enum values fail locally.

## Development

```sh
npm ci
npm test
npm run generate:check
npm pack
npm run smoke
```

Generation needs Python 3, Java 11+ and the repository's pinned OpenAPI snapshot. `scripts/generate.mjs` invokes the root generator bootstrap, verifying/downloading OpenAPI Generator 7.26.0. Generated files live in `src/generated`; never edit them. Generation checks content and file-set drift.

Settings: `typescript-fetch`, `withoutRuntimeChecks=true`, `modelPropertyNaming=original`, `hideGenerationTimestamp=true`, `supportsES6=true`, `importFileExtension=.js`. Reproducible adaptations repair the generator's empty `ExpectedAmount` primitive union, add unknown-field index signatures to response models, and open response enum types while retaining strict input enums. Generated comments are removed uniformly. Runtime parsing stays lossless for unknown keys and enum strings; API validation still controls other request constraints.

Custom HTTPS `baseURL` and injected `fetch` support integration tests. Plain HTTP is allowed only for literal loopback hosts with `allowInsecureLocalhost: true`. Browser and CommonJS builds are not included. The supported runtime baseline is Node 22; local verification passes on Node 22.12.0 and Node 23.5.0 on macOS; the repository CI matrix is configured for Node 22 on Linux, macOS and Windows.

Before stable release, resolve the backend contract notes in `api/contract-notes.md`, verify package ownership and release metadata, and confirm resize response/transition semantics. Dashboard-only capabilities include token management, cards, invoice payment, backups/snapshots, VNC and crypto payments. Server creation can enable backups.

API compatibility targets `/v1`. After 1.0, public deprecations remain for at least one minor release and removals require a new major version. See `CHANGELOG.md`.
