# Arct Cloud SDKs and CLI

CLI, Go client, Python SDK, and TypeScript/JavaScript SDK for the [Arct Cloud API](https://docs.arct.cloud/api-reference/introduction).

All clients cover the 22 public operations: account, servers, locations, plans, images, SSH keys, and invoices. Preview source is available from [ArctCloud/sdk](https://github.com/ArctCloud/sdk).

Registry previews are available from [PyPI](https://pypi.org/project/arct-cloud/0.1.0rc3/) and [npm](https://www.npmjs.com/package/@arct-cloud/sdk).

| Package | Preview | Requirements |
| --- | --- | --- |
| [CLI](docs/cli.md) | `0.1.0rc3` | Python 3.11+; macOS/Linux installer, Windows package |
| [Go client](go/README.md) | Source checkout | Go 1.23+ |
| [Python SDK](python/README.md) | `0.1.0rc3` | Python 3.11+ |
| [TypeScript SDK](typescript/README.md) | `0.1.0-rc.4` | Node.js 22+ |

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

## CLI

On macOS or Linux with Python 3.11+:

```bash
curl -fsSL https://raw.githubusercontent.com/ArctCloud/sdk/main/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
arct --version
arct account get
arct servers list --output json
```

The installer creates a private user environment and configures shell PATH. Rerun it to update; existing auth contexts remain compatible. On Windows, install `arct-cloud==0.1.0rc3` with Python and use `arct` or `python -m arct`.

Table/JSON output, saved contexts, pagination and operation waiting are supported. Commands that charge a card or delete/reinstall a server require confirmation; `--yes` confirms automation. See the [CLI guide](docs/cli.md) for commands, migration and uninstall instructions, or the [hosted CLI documentation](https://docs.arct.cloud/api-reference/cli).

## Python

Install the preview:

```bash
python3 -m pip install "arct-cloud==0.1.0rc3"
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
npm install --save-exact @arct-cloud/sdk@0.1.0-rc.4
```

Alternatively, build a package from the checkout:

```bash
cd typescript
npm ci
npm pack --pack-destination ..
```

From your application directory, install the resulting tarball with `npm install --save-exact /path/to/sdk/arct-cloud-sdk-0.1.0-rc.4.tgz`.

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

See [release setup](docs/releasing.md) for CI, trusted publishing, tag conventions, and CLI package distribution. The Go client currently uses a local module path; public vanity hosting is not configured.
