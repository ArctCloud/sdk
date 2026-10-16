# Arct Cloud SDKs and CLI

Go CLI, Python SDK, and TypeScript/JavaScript SDK for the [Arct Cloud API](https://docs.arct.cloud/api-reference/introduction).

All clients cover the 22 public operations: account, servers, locations, plans, images, SSH keys, and invoices. The packages are being prepared for their first release; the commands below install from this checkout.

| Package | Interface | Requirements |
| --- | --- | --- |
| [Go CLI](go/README.md) | `arct` | Standalone executable; Go 1.23+ to build locally |
| [Python SDK](python/README.md) | `from arct import Arct, AsyncArct` | Python 3.11+ |
| [TypeScript SDK](typescript/README.md) | `import { Arct } from '@arct-cloud/sdk'` | Node.js 22+ |

Create a token in Dashboard > Settings > API Tokens. API access must be enabled on your account. Use read-only tokens for read-only jobs; keep tokens out of browser code and source control.

```bash
export ARCT_TOKEN="arct_your_token_here"
```

## Go CLI

```bash
cd go
go build -o arct ./cmd/arct
./arct --help
./arct account get
./arct servers list --output json
./arct plans list --location fra
```

The CLI supports table and JSON output, named credential contexts, explicit pagination, operation waiting, and noninteractive use. Commands that charge a card or delete/reinstall a server require confirmation; `--yes` is the explicit automation option. See the package README for all commands and flags.

## Python

```bash
python3 -m pip install ./python
```

```python
from arct import Arct

with Arct() as client:
    for server in client.servers.list():
        print(server.hostname, server.status)
```

`AsyncArct` provides async calls and iteration. Models use Pydantic, money uses `Decimal`, and one-time passwords use `SecretStr`. See [Python usage](python/README.md) for creation, waiting, and error handling.

## TypeScript / JavaScript

Build and pack the SDK, then install the resulting tarball in your application:

```bash
cd typescript
npm ci
npm pack
```

```typescript
import { Arct } from '@arct-cloud/sdk';

const client = new Arct();
for await (const server of client.servers.list()) {
  console.log(server.hostname, server.status);
}
```

See [TypeScript usage](typescript/README.md) for options, cancellation and typed errors.

## Payment and operation semantics

Creating and resizing servers can charge a saved card. Retry policy is operation-specific: charge-unknown errors are never retried, create retries preserve the original request/hostname, and ambiguous mutation outcomes are reported explicitly. Resize submits an expected quote to prevent silently accepting a changed price.

An accepted request is not necessarily a completed operation. Waiting has a deadline and can be cancelled without cancelling the server operation. One-time passwords are redacted by default; the CLI requires `--show-password` to intentionally output them.

Token management, card management, invoice payment, backup/snapshot management, password reset, VNC, and crypto payments remain dashboard-only. Server creation can enable backups, and the API supports scheduled deletion and cancelling it.

## Development

Install Go 1.23+, Python 3.11+, uv, Node.js 22+, and Java 21+. Generation downloads a pinned, SHA-256-verified OpenAPI Generator jar into `.tools/`.

```bash
make install
make check
mkdir -p build
make build
```

`make check` verifies the normalized contract, generated files, and all package tests. The shared [fixtures](api/test-cases.json) include all 42 documented API error codes. Tests use local transports and never make purchases.

The snapshot and explicit compatibility overlay live in [api/](api/contract-notes.md). Outstanding upstream schema issues are recorded there; they must be confirmed before declaring stable backend compatibility. Each package documents its generator adaptations.

See [release setup](docs/releasing.md) for CI, trusted publishing, tag conventions, and binary distribution. Registry ownership, trusted-publisher setup and public Go module hosting are external release prerequisites. The local module path is not a claim that vanity hosting is configured.
