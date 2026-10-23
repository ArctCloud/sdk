# Releases

The source repository is [ArctCloud/sdk](https://github.com/ArctCloud/sdk). The published previews use Python and CLI `0.1.0rc3` and TypeScript `0.1.0-rc.4`. This checkout prepares Python/CLI `0.1.0rc4`, TypeScript `0.1.0-rc.5`, and Go source preview `0.1.0-rc.3`; these bumps are not registry publication. The Python package now ships the CLI; no new Go CLI binaries are published. Historical [CLI `0.1.0-rc.2`](https://github.com/ArctCloud/sdk/releases/tag/cli-v0.1.0-rc.2) releases and tags remain unchanged. The initial CLI `rc.1` workflow was cancelled after CI found a timing-sensitive test fixture; it has no published binaries. Release tags are not moved. Stable 1.0.0 requires the contract and acceptance gates in the [design](superpowers/specs/2026-10-17-sdk-cli-design.md).

The GitHub release environments are configured with required maintainer review and package-specific tag rules. Registry authentication and trusted-publisher configuration must be verified separately before pushing Python or TypeScript release tags. A repository push alone does not publish a package.

Python `0.1.0rc1` is published through the `pypi` trusted publisher; its wheel and source attestations and a clean PyPI installation are verified. TypeScript `0.1.0-rc.1` was published locally to establish the npm package, without CI provenance. TypeScript `0.1.0-rc.2` uses the `npm` trusted publisher and release workflow. Do not push a release tag for the already-published bootstrap version.

The organization currently disables pull-request creation by GitHub Actions. Specification drift checks can run, but automated update PRs require that organization setting to be enabled by an owner.

## Repository setup

1. Push the reviewed project to its intended GitHub repository. Enable GitHub Actions on GitHub-hosted runners. The workflows pin third-party action revisions by full commit SHA; review their upstream release notes when updating them.
2. Require the `CI` generation job and all three package matrix jobs before merging. Protect release tags so only release maintainers can create them. Review workflow changes as release code.
3. Create `pypi` and `npm` environments with required reviewers and deployment tag rules for `python-v*` and `typescript-v*`, respectively. The historical `github-release` environment is no longer used for CLI publication. Environment creation and reviewer rules are external configuration; declaring an environment name in YAML does not install those protections.
4. For the daily specification PR, allow GitHub Actions to create pull requests and grant this workflow its declared contents, pull-request, and Actions permissions. It uses the temporary repository token, never a registry credential. The `automation/openapi-update` branch is reserved for this workflow.

Every release calls the complete reusable CI workflow at its tagged commit. Generation must match the checked-in contract; package tests, builds, wheel/tarball installation, and installed Python CLI smoke tests must pass on Linux, macOS, and Windows. CI uses the current stable Go toolchain; the module's compatibility floor remains Go 1.23. The Go race detector runs on Linux. Release building and publication use separate jobs; only publication jobs receive OIDC or release-write permissions. No release job receives an Arct API token.

## PyPI

Verify ownership of `arct-cloud` on PyPI. Configure a GitHub trusted publisher with owner `ArctCloud`, repository `sdk`, workflow filename `release.yml`, and environment `pypi`. A [pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/) can create a new project through its first authorized release. PyPI and TestPyPI have separate publisher configurations; this workflow targets production PyPI.

The [official publication action](https://docs.pypi.org/trusted-publishers/using-a-publisher/) authenticates with the job's short-lived OIDC identity. It uploads wheel and source distributions and [generates PyPI attestations](https://docs.pypi.org/attestations/producing-attestations/). Do not add a PyPI API token to this workflow.

Update `python/pyproject.toml`, `python/uv.lock`, `python/src/arct/__init__.py`, and its changelog before tagging. The tag must exactly match the project version, for example `python-v0.1.0rc4` for version `0.1.0rc4` or `python-v0.1.0` for version `0.1.0`.

## npm

Verify ownership of the `@arct-cloud` organization and `@arct-cloud/sdk` package. If the package does not yet exist, its owner must arrange its first publication separately before configuring a trusted publisher through package settings; these workflows do not reserve package names. Do not publish a placeholder to establish ownership.

Keep `typescript/package.json`'s `repository.url` set to `https://github.com/ArctCloud/sdk.git`; the release build verifies it. npm provenance requires a public source repository and public package. Configure the package's GitHub trusted publisher with owner `ArctCloud`, repository `sdk`, workflow filename `release.yml`, and environment `npm`, allowing direct `npm publish`. Current npm configurations must complete their first successful publication within two days or be recreated. See [npm's trusted-publisher requirements](https://docs.npmjs.com/trusted-publishers/).

The release workflow uses Node.js 22 and explicitly installs npm 11.5.1, meeting npm's minimum Node.js 22.14.0/npm 11.5.1 requirements. Publication uses OIDC and provenance without `NPM_TOKEN` or `NODE_AUTH_TOKEN`. Once configured, the owner can disable traditional token publishing in npm settings.

Update the package version, lockfile, and changelog before tagging. Tags must match `typescript/package.json`, for example `typescript-v0.1.0-rc.5`. Prereleases use npm's `next` dist-tag; stable versions use `latest`.

## CLI package and installer

The CLI is released with `arct-cloud`, using the same version and protected PyPI release as the SDK. A matching `python-v0.1.0rc4` tag publishes the package containing both `arct` and `python -m arct`; `cli-v*` tags no longer trigger publication. Keep `install.sh` pinned to the published `0.1.0rc3` while preparing the next release. Advance the installer pin and matching installer tests only after publishing and verifying the new Python package. Retain old tags, releases and binary assets as history.

Publish and verify the Python package before announcing the installer one-liner or publishing hosted instructions that depend on it. Check a clean registry installation with both `arct --version` and `python -m arct --version`, then verify the [repository installer](https://raw.githubusercontent.com/ArctCloud/sdk/main/install.sh) on macOS/Linux and the [hosted CLI guide](https://docs.arct.cloud/api-reference/cli). The one-liner installs the pinned package in a private user environment; Windows uses the package entry point or module invocation.

```sh
curl -fsSL https://raw.githubusercontent.com/ArctCloud/sdk/main/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
arct --version
```

After publishing and verifying the prepared packages, update `api-reference/sdks.mdx` and `api-reference/cli.mdx` in `ArctCloud/docs` with the published versions, datacenter discovery, filters and placement examples.

Test installer reruns and failed installations with temporary homes. The installer must preserve a working command, avoid duplicate PATH entries and retain credential/config compatibility. It does not replace unrelated binaries at `~/.local/bin/arct`; see [migration and uninstall](cli.md#migrate-update-or-uninstall).

## Local verification

Use Python 3.11+, Node.js 22+, Go 1.23+, and Java 21+.

```sh
make install
make check
python3 -m unittest discover -s scripts -p 'release_*_test.py' -v
sh -n install.sh
python3 -m unittest discover -s scripts -p 'install_test.py' -v
cd python && uv build && cd ..
python3 scripts/release_smoke.py python
python3 scripts/release_smoke.py typescript
```

`scripts/release_check.py` validates a proposed tag locally without publishing:

```sh
GITHUB_REF_NAME=python-v0.1.0rc4 python3 scripts/release_check.py python
GITHUB_REF_NAME=typescript-v0.1.0-rc.5 python3 scripts/release_check.py typescript
```

Push a reviewed matching tag only after ownership and the appropriate environment and publisher have been configured. Tag pushes trigger publication after checks and the environment gate; no additional workflow dispatch is required.

## Specification drift and optional live checks

`spec-drift.yml` fetches the public upstream specification daily, compares parsed JSON, normalizes through `scripts/prepare_openapi.py`, regenerates all packages with the checksum-verified pinned generator, and opens or updates one PR. Incompatible generation or contract changes still produce a review PR with the failure status. Review the contract overlay, generated diff, shared fixtures, and package behavior before merging; no automatic merge runs. The workflow explicitly dispatches CI on its bot branch because [events generated with `GITHUB_TOKEN` normally do not start another workflow](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow).

The manual `live-smoke.yml` workflow uses a separate `live-readonly` environment. Restrict that environment to the protected default branch and configure `ARCT_READ_TOKEN` as an environment secret only when read-only API access is wanted. With no token the script exits successfully as skipped. It performs fixed-origin GET requests and paginates the datacenter and plan catalogs. Assertions require valid datacenter codes, `ams2` high-performance plans, and legacy `location=ams` results matching the unfiltered Amsterdam plans. It refuses redirects, prints no response bodies or token, and has no mutation code. Normal CI, PR jobs, and release jobs never receive this secret. Local invocation is `python3 scripts/live_smoke.py` with the token supplied through the environment.

Remote GitHub Actions execution, registry authentication, provenance verification, native Linux/Windows execution, and actual publication must be checked in the configured hosted repository. Local macOS tests cannot establish those outcomes.
