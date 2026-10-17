# Arct CLI

[Arct Cloud](https://www.arct.cloud) · [Hosted CLI guide](https://docs.arct.cloud/api-reference/cli) · [SDKs](../README.md)

`arct` covers all 22 public API operations and ships with the Python SDK in `arct-cloud==0.1.0rc3`. Python 3.11+ is required. Commands, flags, saved contexts and credentials remain compatible with the previous Go CLI; historical [binary releases](https://github.com/ArctCloud/sdk/releases/tag/cli-v0.1.0-rc.2) remain available, but new CLI binaries are no longer published.

## Install on macOS or Linux

Install Python 3.11+ with virtual environment support, then run:

```sh
curl -fsSL https://raw.githubusercontent.com/ArctCloud/sdk/main/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
arct --version
```

The installer pins `arct-cloud==0.1.0rc3` in a private virtual environment under `~/.local/share/arct/` and exposes `~/.local/bin/arct`. It needs no sudo and leaves your system Python packages alone. It adds PATH setup to the zsh configuration or Bash startup files; other shells require manual PATH setup. Run the printed export in your current terminal because an installer cannot change its parent shell. `arct --version` reports `0.1.0rc3`.

Rerun the same installer to update to its pinned release or repair an installation. A failed package installation leaves the existing command available, and reruns do not duplicate shell profile entries.

## Install on Windows or in a Python environment

Install into your chosen Python 3.11+ environment:

```sh
python -m pip install "arct-cloud==0.1.0rc3"
python -m arct --version
python -m arct --help
```

The package also installs the `arct` console command. If its scripts directory is on PATH, use `arct`; otherwise replace `arct` in the examples below with `python -m arct`. On Windows, `py -3.11` can replace `python` when selecting the interpreter.

For source development, run `python -m pip install ./python` from the repository root.

## Migrate, update or uninstall

Existing saved credentials and active contexts are reused without conversion. The installer refuses to replace an unrelated executable or symlink at `~/.local/bin/arct`. If your previous Go binary is there, move it aside before running the installer:

```sh
mv "$HOME/.local/bin/arct" "$HOME/.local/bin/arct-go"
```

After installation, check `command -v arct` and `arct --version`. If an older binary elsewhere takes precedence, put `~/.local/bin` first on PATH or remove that old binary, then open a new terminal.

For a package installation, update with `python -m pip install --upgrade "arct-cloud==0.1.0rc3"` and uninstall with `python -m pip uninstall arct-cloud`, using the same interpreter/environment.

For the shell installation, remove its command and private environment:

```sh
rm "$HOME/.local/bin/arct"
rm -rf "$HOME/.local/share/arct"
```

Remove the installer-added PATH line from your shell profile if no longer needed. Uninstalling retains saved credentials; use `arct auth logout` or `arct context delete NAME` before uninstalling to remove a saved context. These local commands do not revoke dashboard tokens.

## Read resources

```sh
export ARCT_TOKEN='your-dashboard-created-token'
arct account get
arct servers list --output json
arct servers list --location fra --all --columns id,hostname,status
```

## Mutations and command controls

The following examples can charge a card, destroy data or change billing. `--yes` explicitly confirms each mutation:

```sh
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

Use `--ssh-key ''` for an explicit empty SSH-key array (password installation), `--label ''` to clear labels, and `--coupon-code-null` for a null coupon. Omitted arrays remain omitted. Boolean false requires `--enable-backups=false` or `--delete-protection=false`. Label requests retain the contract's maximum of 100; upstream prose says 10 and needs clarification.

## Output, waiting and errors

Default lists request one page with API defaults. `--all` emits an array; page JSON retains `data` and `pagination`. `--output json` emits complete results with redacted secrets. Table output supports `--columns id,hostname,status` and `--no-header`. Prompts, progress, billing information and errors use stderr.

`--wait` supports create/start/stop/restart/reinstall/resize/immediate-delete. Immediate deletion waits for an acknowledged deletion to return `404`; scheduled deletion does not support waiting. Default polling is 5 seconds; default waiting deadline is 600 seconds. `--timeout 30s` or `--timeout 30` changes that deadline. Accepted operations continue after interruption or timeout. Restart/reinstall require an observed transition to avoid accepting stale `running` data. Resize waits for no pending resize and the requested final plan; it never stops or starts a server. Pending payment is reported explicitly. Pre-orders may exceed the deadline.

Resize obtains the quote before confirmation and sends that exact amount unchanged. A `price_changed` conflict requires a new decision. The CLI does not expose the SDK's null price-check opt-out.

After a successful server wait, table output shows the final server fields and preserves order/password details. JSON retains the original response alongside `final_server`; resize adds `final_resize_options`, and immediate deletion adds `deleted: true`. Waiting failures print the original result with `wait_error` and exit nonzero. Passwords are redacted unless `--show-password` explicitly opts in on create/reinstall; this also applies after waiting fails. Tokens remain redacted even with `--show-password`. Capture any revealed one-time password securely.

Charge-unknown markers (`order_intent_id` or `payment_pending`) stop automatic retries. Preserve support identifiers and reconcile billing before repeating a purchase. A lost response or matching hostname cannot prove a successful order.

Exit codes: `0` success/accepted, `1` API/network failure, `2` invalid input/missing confirmation, `3` timeout/uncertain outcome/unknown charge, `130` interruption. JSON errors are structured on stderr; progress can precede them.

## Local credentials and endpoint

```sh
arct auth login --context production
arct auth status
arct context list
arct context use production
arct auth logout --context production
arct context delete production
```

Login validates an existing dashboard token; tokens are read from `ARCT_TOKEN` or stdin (hidden on a terminal). Token command-line flags are unsupported. Logout removes local credentials without remotely revoking the token. `ARCT_TOKEN` overrides saved credentials; `--context NAME` selects a saved context. The credential JSON schema is unchanged: `active`, with named `contexts` containing `token` and optional `base_url`. `$XDG_CONFIG_HOME/arct/config.json` takes precedence when set; otherwise:

| Platform | Credential file |
| --- | --- |
| Linux | `~/.config/arct/config.json` |
| macOS | `~/Library/Application Support/arct/config.json` |
| Windows | `%APPDATA%\arct\config.json` |

POSIX credentials use file mode `0600` and directory mode `0700`. Windows uses a protected DACL granting only the current user and SYSTEM; unsupported ACL enforcement fails before writing credentials.

Production uses `https://api.arct.cloud/v1`. `--base-url` or `ARCT_BASE_URL` selects another HTTPS endpoint; plain HTTP is allowed only for explicit localhost tests. Redirects are rejected. Prefer read-only tokens for reads. Token issuance/revocation, cards, invoice payment, password resets, backup/snapshot management, VNC and crypto payments remain dashboard operations.

Global flags may appear before or after the resource/action. Use `arct --help` or `arct RESOURCE ACTION --help` for command-specific help. `--context` selects credentials, `--base-url` selects an endpoint, and `--output`, `--columns`, `--no-header`, `--timeout`, `--yes`, `--wait` and `--show-password` apply where supported.
