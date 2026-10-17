# Arct Cloud Go client

[Arct Cloud](https://www.arct.cloud) · [API reference](https://docs.arct.cloud/api-reference/introduction) · [SDK source](https://github.com/ArctCloud/sdk)

Go 1.23+ client for all 22 public API operations under `/v1`. Set `ARCT_TOKEN` to a dashboard-created API token; prefer read-only tokens for queries. Creating or resizing servers can charge the saved card. Client methods do not prompt.

For terminal commands, install the Python-based [Arct CLI](../docs/cli.md). Historical Go CLI releases remain available; this package retains the Go API client and its tests.

## Usage

Public vanity hosting for `arct.cloud/sdk/go` is not configured. Use the client from this checkout or a local Go module `replace` directive; there is no supported public `go get` installation yet.

```go
package main

import (
    "context"
    "fmt"

    arct "arct.cloud/sdk/go"
)

func main() {
    client, err := arct.New(arct.Options{})
    if err != nil { panic(err) }
    ctx := context.Background()
    for server, err := range client.Servers.List(ctx, arct.Params{"location": "fra"}) {
        if err != nil { panic(err) }
        fmt.Println(server["id"], server["status"])
    }
}
```

Resources expose all operations; `List` returns a lazy Go iterator (100 items per page by default), `ListPage` returns an exact page, and `Client.All` collects pages. `Params` preserves omitted fields, explicit null and empty arrays. Results preserve unknown fields/statuses and use `json.Number` for exact numeric tokens. Generated typed models and endpoint transport reside in `internal/generated`; the public lossless resource facade avoids generated nullable/default coercions.

Use `client.Servers.Create(ctx, arct.Params{...})`, `client.Servers.Resize(ctx, id, plan)` for automatic quoting, or `Resize(ctx, id, plan, json.Number("4.12"))` to supply a quote. An explicit `Resize(ctx, id, plan, nil)` forwards JSON null as the API's deliberate price-check opt-out; the CLI does not expose that opt-out. `Secret.Reveal()` deliberately unwraps a password. Default JSON/string representations redact secrets. `Wait` and `WaitCreated` retain original results. `Options.HTTPClient` permits transport injection; requests have finite timeouts and honor context cancellation.

Reads and create requests use at most three total attempts. Charge markers always stop retries. Create retries send identical bodies and hostnames. A retried `hostname_taken` is uncertain and never becomes a fabricated order/password. Other mutation failures are not blindly retried. `429` honors `Retry-After`, bounded by the context deadline. Changed resize quotes require a new decision.

Process-local scheduling enforces reads120/minute/token, writes30/minute/token/account, and paid operations5/minute plus20/hour/token/account. Paid calls also consume writes. The first mutation automatically resolves account identity through a read; concurrent clients share account budgets across tokens and avoid duplicate identity reads for a token. Separate processes rely on server limits.

## Generation and checks

```sh
python3 go/scripts/generate.py
python3 go/scripts/generate.py --check
cd go
go test -race ./...
go vet ./...
```

Run generation from the repository root. The shared bootstrap verifies OpenAPI Generator7.26.0 by SHA256. A temporary compatibility document converts nullable OpenAPI3.1 unions to3.0.3 and uses open JSON request/response envelopes for generated transport; original model schemas remain generated. This preserves unset/null/empty distinctions, unknown response values and exact monetary tokens in the policy facade. No generated files are patched. `--check` compares bytes and the complete generated file set without replacing checked-in output.

The API overlay and unresolved backend issues are documented in `../api/contract-notes.md`. No tests perform live mutations.
