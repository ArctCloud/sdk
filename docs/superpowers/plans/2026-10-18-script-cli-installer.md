# Script CLI Installer Implementation Plan

> **For agentic workers:** Use the existing subagent execution method. Preserve assigned file ownership and other workers' edits.

**Goal:** Replace binary CLI distribution with a repository shell installer and an SDK-backed Python CLI.

**Architecture:** The `arct-cloud` wheel contains the CLI console entry point. A POSIX shell installer installs its pinned version into a private user environment and exposes `arct` on PATH. Existing SDK transport, validation, retries and operation waiters remain authoritative.

**Tech Stack:** Python 3.11+, argparse, existing HTTPX/Pydantic, POSIX shell, existing GitHub Actions/PyPI publishing.

**Spec:** `docs/superpowers/specs/2026-10-18-script-cli-design.md`

## Global Constraints

- English code, documentation and tool output; no new runtime dependencies.
- Preserve CLI command/config compatibility, exact billing values, confirmation and secrets behavior.
- `arct-cloud` and CLI version: `0.1.0rc3`; TypeScript remains `0.1.0-rc.4`.
- Shell installation supports macOS/Linux; package entry points also support Windows.
- No live mutations. Preserve old public tags/releases and user files.

## Review Focus

- Existing credential files, permissions and Windows ACL handling must remain compatible (Task 1).
- Global flags before/after subcommands and omitted/empty/false/null fields must retain meaning (Task 1).
- Interrupted waiting must retain accepted results without replaying a mutation (Task 1).
- Failed installation, repeat installation, spaces in HOME and profile duplication (Task 2).
- Installed artifact and release version must agree; no binary release path may remain active (Task 3).

## Task 1: Python CLI parity

Files: `python/src/arct/_cli.py`, `python/src/arct/_cli_config.py` if useful, `python/src/arct/__main__.py`, `python/tests/test_cli.py`.

Interface: `main(argv=None) -> int`; console script and module invocation call the same function. Reuse `Arct` and public SDK models/errors. Tests may inject a client factory/HTTPX transport without a new public flag.

- [x] Port meaningful command, config, billing, output, wait and error tests from `go/internal/cli/cli_test.go`; establish failures before implementation.
- [x] Implement command parsing and dispatch with argparse; preserve all 22 API operations and local auth/context commands.
- [x] Preserve platform config paths, private atomic writes, secret filtering and signal exit behavior.
- [x] Run focused CLI tests and existing Python tests; report exact commands/results.
- [x] Independently review task diff and fix material findings.

## Task 2: User installation

Files: `install.sh`, `scripts/install_test.py`.

Interface: executable POSIX shell script, usable through `curl ... | sh`; installs `arct-cloud==0.1.0rc3` using Python 3.11+ and exposes `~/.local/bin/arct`. No sudo, runtime download or Go build. Default installation is user-local and version-pinned.

- [x] Write installer checks using temporary HOME and controlled command stubs: unsupported Python, failed pip, repeated install, spaces, PATH/profile handling.
- [x] Implement safe staging and command replacement; successful reruns reuse or replace only installer-owned data. Failed install preserves the working command. Append shell PATH setup idempotently and print current-shell activation.
- [x] Run shell syntax checks and installer tests; perform a real wheel install in a temporary HOME after Task 3 builds the package.
- [x] Independently review installer diff and fix material findings.

## Task 3: Packaging and documentation

Files: Python metadata/version/lock/changelog; `scripts/release_{check,checks_test,smoke}.py`; `.github/workflows/{ci,release}.yml`; `Makefile`; root/Python/Go READMEs; `docs/cli.md`; `docs/releasing.md`; hosted docs checkout CLI/SDK guides.

- [x] Add the console entry point, bump Python to `0.1.0rc3`, update the lock and changelog.
- [x] Make installed-wheel smoke test both `arct --help/--version` and module invocation on all three platforms.
- [x] Remove binary release jobs/tag trigger/builder and replaced Go CLI files after the replacement tests pass. Keep Go SDK tests and generation.
- [x] Update one-line installation, runtime requirement, PATH activation, migration, update/uninstall and Windows package instructions.
- [ ] Run release checks, installer checks, package build/smoke, Python tests, Go checks and required CI.
- [ ] Review complete diff, merge through existing checks, publish Python via existing protected OIDC release, and verify clean registry installation.
- [ ] Verify repository-hosted installer and hosted documentation. Retain previous releases as history.

## Progress

- Design: user selected script installation; Python implementation chosen to reuse the existing SDK.
- Exploration: command parity, credential schema and release integration mapped independently.

- Validation: 294 Python tests (84 CLI), 17 script checks, Go tests/vet, isolated installed-wheel smoke, piped installer in a HOME containing spaces, repeat installation, shell PATH and saved-context compatibility passed.
- Independent review: installer interruption cleanup fixed and regression verified; full migration review passed. Hosted CI and registry publication remain.
