# Releases

The workflows are prepared for publication; no registry ownership, trusted publisher, hosted repository, or release environment has been configured by this project. Package names remain provisional until their owners verify them. Start with a prerelease. Stable 1.0.0 requires the contract and acceptance gates in the [design](superpowers/specs/2026-10-17-sdk-cli-design.md).

## Repository setup

1. Push the reviewed project to its intended GitHub repository. Enable GitHub Actions on GitHub-hosted runners. The workflows pin third-party action revisions by full commit SHA; review their upstream release notes when updating them.
2. Require the `CI` generation job and all three package matrix jobs before merging. Protect release tags so only release maintainers can create them. Review workflow changes as release code.
3. Create `pypi`, `npm`, and `github-release` environments with required reviewers and deployment tag rules for `python-v*`, `typescript-v*`, and `cli-v*`, respectively. Environment creation and reviewer rules are external configuration; declaring an environment name in YAML does not install those protections.
4. For the daily specification PR, allow GitHub Actions to create pull requests and grant this workflow its declared contents, pull-request, and Actions permissions. It uses the temporary repository token, never a registry credential. The `automation/openapi-update` branch is reserved for this workflow.

Every release calls the complete reusable CI workflow at its tagged commit. Generation must match the checked-in contract; package tests, builds, wheel/tarball installation, and native CLI smoke tests must pass on Linux, macOS, and Windows. CI uses the current stable Go toolchain; the module's compatibility floor remains Go 1.23. The Go race detector runs on Linux. Release building and publication use separate jobs; only publication jobs receive OIDC or release-write permissions. No release job receives an Arct API token.

## PyPI

Verify ownership of `arct-cloud` on PyPI. Configure a GitHub trusted publisher for the repository owner, repository name, workflow filename `release.yml`, and environment `pypi`. A [pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/) can create a new project through its first authorized release. PyPI and TestPyPI have separate publisher configurations; this workflow targets production PyPI.

The [official publication action](https://docs.pypi.org/trusted-publishers/using-a-publisher/) authenticates with the job's short-lived OIDC identity. It uploads wheel and source distributions and [generates PyPI attestations](https://docs.pypi.org/attestations/producing-attestations/). Do not add a PyPI API token to this workflow.

Update `python/pyproject.toml`, `python/src/arct/__init__.py`, and its changelog before tagging. The tag must exactly match the project version, for example `python-v0.1.0rc1` for version `0.1.0rc1` or `python-v0.1.0` for version `0.1.0`.

## npm

Verify ownership of the `@arct-cloud` organization and `@arct-cloud/sdk` package. If the package does not yet exist, its owner must arrange its first publication separately before configuring a trusted publisher through package settings; these workflows do not reserve package names. Do not publish a placeholder to establish ownership.

Set `typescript/package.json`'s `repository.url` to the exact `https://github.com/OWNER/REPOSITORY.git` publishing repository URL; the release build verifies it. npm provenance requires a public source repository and public package. Configure the package's GitHub trusted publisher with the exact owner, repository, workflow filename `release.yml`, and environment `npm`, allowing direct `npm publish`. Current npm configurations must complete their first successful publication within two days or be recreated. See [npm's trusted-publisher requirements](https://docs.npmjs.com/trusted-publishers/).

The release workflow uses Node.js 22 and explicitly installs npm 11.5.1, meeting npm's minimum Node.js 22.14.0/npm 11.5.1 requirements. Publication uses OIDC and provenance without `NPM_TOKEN` or `NODE_AUTH_TOKEN`. Once configured, the owner can disable traditional token publishing in npm settings.

Update the package version, lockfile, and changelog before tagging. Tags must match `typescript/package.json`, for example `typescript-v0.1.0-rc.1`. Prereleases use npm's `next` dist-tag; stable versions use `latest`.

## Standalone CLI

Update `go/VERSION` and the CLI changelog, then use the matching tag, for example `cli-v0.1.0-rc.1`. The CLI's `--version` must agree with `go/VERSION`.

The build produces six standalone binaries for Linux, macOS, and Windows on amd64/arm64, with CGO disabled, plus `SHA256SUMS`. After the `github-release` environment gate, the temporary repository token creates a GitHub release and attaches these files. Prerelease tags produce GitHub prereleases. The workflow checks that the tag already exists and does not overwrite an existing release. Download the desired binary, compare its SHA-256 with the published checksum, and grant execute permission on Linux/macOS. This does not configure the Go module's public vanity URL or an OS package manager.

## Local verification

Use Python 3.11+, Node.js 22+, Go 1.23+, and Java 21+.

```sh
make install
make check
python3 -m unittest discover -s scripts -p 'release_*_test.py' -v
cd python && uv build && cd ..
python3 scripts/release_smoke.py python
python3 scripts/release_smoke.py typescript
python3 scripts/release_smoke.py cli
```

`scripts/release_check.py` validates a proposed tag locally without publishing:

```sh
GITHUB_REF_NAME=python-v0.1.0 python3 scripts/release_check.py python
GITHUB_REF_NAME=typescript-v0.1.0 python3 scripts/release_check.py typescript
GITHUB_REF_NAME=cli-v0.1.0 python3 scripts/release_check.py cli
```

Push a reviewed matching tag only after ownership and the appropriate environment and publisher have been configured. Tag pushes trigger publication after checks and the environment gate; no additional workflow dispatch is required.

## Specification drift and optional live checks

`spec-drift.yml` fetches the public upstream specification daily, compares parsed JSON, normalizes through `scripts/prepare_openapi.py`, regenerates all packages with the checksum-verified pinned generator, and opens or updates one PR. Incompatible generation or contract changes still produce a review PR with the failure status. Review the contract overlay, generated diff, shared fixtures, and package behavior before merging; no automatic merge runs. The workflow explicitly dispatches CI on its bot branch because [events generated with `GITHUB_TOKEN` normally do not start another workflow](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow).

The manual `live-smoke.yml` workflow uses a separate `live-readonly` environment. Restrict that environment to the protected default branch and configure `ARCT_READ_TOKEN` as an environment secret only when read-only API access is wanted. With no token the script exits successfully as skipped. It performs seven fixed-origin GET requests, refuses redirects, prints no response bodies or token, and has no mutation code. Normal CI, PR jobs, and release jobs never receive this secret. Local invocation is `python3 scripts/live_smoke.py` with the token supplied through the environment.

Remote GitHub Actions execution, registry authentication, provenance verification, native Linux/Windows execution, and actual publication must be checked in the configured hosted repository. Local macOS tests and cross-compilation cannot establish those outcomes.
