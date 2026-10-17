# Script CLI and installer

The user replaces the Go binary distribution requirement with a repository-hosted shell installer for a Python or Node CLI. Python is the implementation choice because the existing synchronous SDK already covers every API operation.

- Ship `arct` through the existing `arct-cloud` Python package, version `0.1.0rc3`, with `arct = "arct._cli:main"`. Require Python 3.11+. Do not add a CLI framework or duplicate the SDK transport.
- Provide `curl -fsSL https://raw.githubusercontent.com/ArctCloud/sdk/main/install.sh | sh`. Install the pinned package in a user-owned virtual environment, expose `~/.local/bin/arct`, and configure the user's shell PATH without sudo. Print the command needed by the current terminal, which a child process cannot modify.
- Support the shell installer on macOS and Linux. Preserve Python CLI support on Windows through the package's console entry point and `python -m arct`; document package installation there.
- Preserve all 22 API operations and existing CLI commands, flags, confirmation rules, output modes, wait semantics, explicit false/null/empty values, exact resize amounts and exit codes 0/1/2/3/130.
- Preserve the credential JSON schema and platform-specific locations. Keep credentials private, reject unsafe file types, write atomically, hide prompted tokens, and never reveal tokens through `--show-password`.
- Retain the original create/reinstall result on successful or failed waiting. Immediate deletion waits for 404; resize quotes are obtained before confirmation and sent unchanged.
- Installer reruns must be safe: failed installs leave an existing working command available; profile entries are not duplicated; paths containing spaces work. Use a pinned published package and HTTPS without disabling certificate validation.
- Stop building and publishing Go CLI binaries. Remove the replaced Go CLI source after parity is verified, keep the Go client and its tests, and retain historical releases/tags.
- Update installation and release documentation, including the hosted CLI guide. Publish the Python package before presenting the one-liner as ready.

Verification uses mocked API tests, temporary home directories, isolated package installations, existing SDK suites, three-platform CI, and a clean installation from the published package. No live mutation is needed.
