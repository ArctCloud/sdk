# Arct Cloud SDKs and CLI

CLI, Go client, Python SDK, and TypeScript/JavaScript SDK for the [Arct Cloud API](https://docs.arct.cloud/api-reference/introduction).

The common SDK facade and CLI surface covers 23 operations: account, servers, datacenters, locations, plans, images, SSH keys, and invoices. The 25-operation live contract snapshot also retains newer credit APIs; support beyond the common surface varies by package. Preview source is available from [ArctCloud/sdk](https://github.com/ArctCloud/sdk).

Published registry previews are Python/CLI `0.1.0rc3` on [PyPI](https://pypi.org/project/arct-cloud/0.1.0rc3/) and TypeScript `0.1.0-rc.4` on [npm](https://www.npmjs.com/package/@arct-cloud/sdk). This checkout prepares the versions below; the datacenter additions require a source installation until publication.

| Package | Prepared source preview | Requirements |
| --- | --- | --- |
| [CLI](docs/cli.md) | `0.1.0rc4` | Python 3.11+; macOS/Linux installer, Windows package |
| [Go client](go/README.md) | `0.1.0-rc.3` (source checkout) | Go 1.23+ |
| [Python SDK](python/README.md) | `0.1.0rc4` | Python 3.11+ |
| [TypeScript SDK](typescript/README.md) | `0.1.0-rc.5` | Node.js 22+ |

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

Install the published Python/CLI `0.1.0rc3` on macOS or Linux with Python 3.11+:

```bash
curl -fsSL https://raw.githubusercontent.com/ArctCloud/sdk/main/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
arct --version
arct account get
arct servers list --output json
```

The installer creates a private user environment and configures shell PATH. Rerun it to update; existing auth contexts remain compatible. Windows users can install `arct-cloud==0.1.0rc3` with Python and use `arct` or `python -m arct`. The installer pin will advance only after the next package is published.

For the prepared datacenter commands, install from this checkout:

```bash
python3 -m pip install ./python
python3 -m arct datacenters list
python3 -m arct plans list --datacenter ams2
```

Prefer `--datacenter ams2` for placement and catalog filters. Deprecated `--location ams` remains compatible and selects the location's default datacenter for the plan tier when creating a server.

Table/JSON output, saved contexts, pagination and operation waiting are supported. Commands that charge a card or delete/reinstall a server require confirmation; `--yes` confirms automation. See the [CLI guide](docs/cli.md) for commands, migration and uninstall instructions, or the [hosted CLI documentation](https://docs.arct.cloud/api-reference/cli).

## Python

Install the published preview (before the datacenter additions):

```bash
python3 -m pip install "arct-cloud==0.1.0rc3"
```

Install the prepared datacenter preview from the checkout:

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

Install the published preview (before the datacenter additions):

```bash
npm install --save-exact @arct-cloud/sdk@0.1.0-rc.4
```

Alternatively, build a package from the checkout:

```bash
cd typescript
npm ci
npm pack --pack-destination ..
```

From your application directory, install the resulting tarball with `npm install --save-exact /path/to/sdk/arct-cloud-sdk-0.1.0-rc.5.tgz`.

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

Token management, card management, backup/snapshot management, password reset, VNC, and crypto payments remain dashboard-only. Invoice payment and newer credit APIs are outside the common CLI/facade surface. Server creation can enable backups, and the API supports scheduled deletion and cancelling it.

## Development

Install Go 1.23+, Python 3.11+, uv, Node.js 22+, and Java 21+. Generation downloads a pinned, SHA-256-verified OpenAPI Generator jar into `.tools/`.

```bash
make install
make check
mkdir -p build
make build
```

`make check` verifies the normalized contract, generated files, and all package tests. The shared [fixtures](api/test-cases.json) include 49 error/status pairs. Tests use local transports and never make purchases.

The snapshot and explicit compatibility overlay live in [api/](api/contract-notes.md). Outstanding upstream schema issues are recorded there; they must be confirmed before declaring stable backend compatibility. Each package documents its generator adaptations.

See [release setup](docs/releasing.md) for CI, trusted publishing, tag conventions, and CLI package distribution. The Go client currently uses a local module path; public vanity hosting is not configured.
