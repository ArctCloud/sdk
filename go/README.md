# Arct Go client and CLI

Go 1.23+, API `/v1`, version 0.1.0. Build locally; the vanity module and public binaries are not published.

```sh
cd go
go build -o arct ./cmd/arct
./arct --version
./arct --help
```

```sh
export ARCT_TOKEN='your-dashboard-created-token'
arct account get
arct servers list --output json
arct servers list --location fra --all --columns id,hostname,status
arct servers create --hostname web-1 --location fra --plan vm.small --image IMAGE_UUID --ssh-key KEY_UUID --yes --wait
arct servers resize-options SERVER_UUID
arct servers resize SERVER_UUID --plan vm.medium --expected-amount 4.12 --yes
arct servers delete SERVER_UUID --at-period-end --yes
arct servers cancel-deletion SERVER_UUID --yes
```

Command IDs must be UUIDs; replace the example placeholders. All 22 API operations are available under `account`, `servers`, `locations`, `plans`, `images`, `ssh-keys`, and `invoices`. `arct RESOURCE ACTION --help` lists applicable flags.

| Command | Request controls |
| --- | --- |
| `servers list` | `--status`, `--location` |
| `plans list`, `images list` | `--location` |
| Every API `list` | `--page`, `--per-page`, `--all` |
| `servers create` | `--hostname`, `--location`, `--plan`, `--image`, `--billing-period`, repeated `--ssh-key`, `--coupon-code` or `--coupon-code-null`, `--enable-backups[=false]` |
| `servers update ID` | `--hostname`, `--delete-protection[=false]`, repeated `--label` |
| `servers delete ID` | `--at-period-end[=false]`, `--yes`, immediate deletion supports `--wait` |
| `servers reinstall ID` | `--image`, `--hostname`, repeated `--ssh-key`, `--yes` |
| `servers resize ID` | `--plan`, `--expected-amount`, `--yes` |
| `ssh-keys create` | `--name`, `--public-key` or `--public-key-file PATH` (`-` reads stdin) |
| `servers wait ID` | `--status`, `--timeout` |

`servers get/start/stop/restart/resize-options/cancel-deletion`, `account get`, `ssh-keys list/get/delete`, `locations list`, and `invoices list/get` complete the operation set. Delete, reinstall, resize, creation and cancellation of scheduled deletion require confirmation; pass `--yes` in automation. SSH key creation and state actions remain scriptable.

Use `--ssh-key ''` for an explicit empty SSH-key array (password installation), and `--label ''` to clear labels. Omitted arrays remain omitted. Boolean false requires `--enable-backups=false` or `--delete-protection=false`. Label requests retain the contract's maximum of 100; upstream prose says 10 and needs clarification.

Default lists request one page with API defaults. `--all` emits an array; page JSON retains `data` and `pagination`. `--output json` emits complete results with redacted secrets. Table output supports `--columns id,hostname,status` and `--no-header`. Prompts, progress, billing information and errors use stderr.

`--wait` supports create/start/stop/restart/reinstall/resize/immediate-delete. Default polling is 5 seconds; default waiting deadline is 600 seconds. `--timeout 30s` or `--timeout 30` changes that deadline. Accepted operations continue after interruption or timeout. Restart/reinstall require an observed transition to avoid accepting stale `running` data. Resize waits for no pending resize and the requested final plan; it never stops or starts a server. Pending payment is reported explicitly. Pre-orders may exceed the deadline.

Create/reinstall results retain their original order/password alongside `final_server`. Waiting failures also print the original result with `wait_error` and exit nonzero. Passwords are redacted unless `--show-password` explicitly opts in on create/reinstall; this also applies after waiting fails. Tokens remain redacted. Capture any revealed one-time password securely.

Exit codes: 0 success/accepted, 1 API/network failure, 2 invalid input/missing confirmation, 3 timeout/uncertain outcome/unknown charge, 130 interruption. JSON errors are structured on stderr; progress can precede them.

## Local credentials

```sh
arct auth login --context production
arct auth status
arct context list
arct context use production
arct auth logout --context production
arct context delete production
```

Login validates an existing dashboard token; tokens are read from `ARCT_TOKEN` or stdin (hidden on a terminal). Token command-line flags are unsupported. Logout removes local credentials without remotely revoking the token. `ARCT_TOKEN` overrides saved credentials; `--context NAME` selects a saved context. Configuration uses the OS user configuration directory (`$XDG_CONFIG_HOME/arct/config.json` where set). POSIX credentials use file0600/directory0700. Windows uses a protected DACL granting only the current user and SYSTEM; unsupported ACL enforcement fails before writing credentials.

Production uses `https://api.arct.cloud/v1`. `--base-url` or `ARCT_BASE_URL` selects another HTTPS endpoint; plain HTTP is allowed only for explicit localhost tests. Redirects are rejected. Prefer read-only tokens for reads. Token issuance/revocation, cards, invoice payment, password resets, backup/snapshot management, VNC and crypto payments remain dashboard operations.

## Go client

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

Use `CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build ./cmd/arct` for cross-compilation; Linux/macOS/Windows amd64/arm64 are supported build targets. Non-native executables require their platform for runtime validation. The API overlay and unresolved backend issues are documented in `../api/contract-notes.md`. No tests perform live mutations.
