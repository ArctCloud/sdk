# Arct Cloud SDKs and CLI

Go CLI, Python SDK, and TypeScript/JavaScript SDK for the [Arct Cloud API](https://docs.arct.cloud/api-reference/introduction).

All clients cover the 22 public operations: account, servers, locations, plans, images, SSH keys, and invoices. Preview source is available from [ArctCloud/sdk](https://github.com/ArctCloud/sdk).

| Package | Preview | Requirements |
| --- | --- | --- |
| [Go CLI](go/README.md) | `0.1.0-rc.2` | Standalone executable; Go 1.23+ only for source builds |
| [Python SDK](python/README.md) | `0.1.0rc1` | Python 3.11+ |
| [TypeScript SDK](typescript/README.md) | `0.1.0-rc.1` | Node.js 22+ |

Create a token in Dashboard > Settings > API Tokens. API access must be enabled on your account. Use read-only tokens for read-only jobs; keep tokens out of browser code and source control.

```bash
export ARCT_TOKEN="arct_your_token_here"
```

## Source checkout

For development or source installation:

```bash
git clone https://github.com/ArctCloud/sdk.git
cd sdk
```

The source commands below start from this checkout's root.

## Go CLI

Download the binary for your platform from [CLI preview 0.1.0-rc.2](https://github.com/ArctCloud/sdk/releases/tag/cli-v0.1.0-rc.2), verify it against `SHA256SUMS`, and install it as `arct` on your `PATH`. Linux, macOS and Windows each have amd64 and arm64 assets. See [installation commands](go/README.md#install-the-preview).

Alternatively, build from the checkout:

```bash
go -C go build -o ../arct ./cmd/arct
./arct --version
```

With the binary installed on your `PATH`:

```bash
arct --version
arct account get
arct servers list --output json
arct plans list --location fra
```

The CLI supports table and JSON output, named credential contexts, explicit pagination, operation waiting, and noninteractive use. Commands that charge a card or delete/reinstall a server require confirmation; `--yes` is the explicit automation option. See the package README for all commands and flags. Source builds are also supported; public vanity hosting for `arct.cloud/sdk/go` is not configured.

## Python

Install the preview:

```bash
python3 -m pip install "arct-cloud==0.1.0rc1"
```

Alternatively, install from the checkout:

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

Install the exact preview version in your application:

```bash
npm install --save-exact @arct-cloud/sdk@0.1.0-rc.1
```

Alternatively, build a package from the checkout:

```bash
cd typescript
npm ci
npm pack --pack-destination ..
```

From your application directory, install the resulting tarball with `npm install --save-exact /path/to/sdk/arct-cloud-sdk-0.1.0-rc.1.tgz`.

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

See [release setup](docs/releasing.md) for CI, trusted publishing, tag conventions, and binary distribution. The Go client currently uses a local module path; public vanity hosting is not configured.
