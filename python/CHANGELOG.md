# Changelog

## 0.1.0rc4 (unreleased)

- Add datacenter discovery, create placement and catalog/server filters to sync/async SDKs and the CLI.
- Preserve legacy location calls with deprecation warnings and tolerate absent/null datacenter response fields.
- Match datacenter placement and legacy aliases during uncertain create reconciliation without inferring success or repeating a conflicting creation.
- Regenerate from the live API contract, including account credit responses and operations; older account responses remain accepted.

## 0.1.0rc3 (preview)

- Add the `arct` command and `python -m arct`, reusing the Python SDK and existing credential contexts.
- Add a repository-hosted shell installer for macOS and Linux; replace Go CLI binary distribution.

## 0.1.0rc2 (preview)

Add Arct Cloud website and documentation links to the package page. SDK runtime behavior is unchanged.

## 0.1.0rc1 (preview)

Initial Python 3.11+ sync and async SDK for all 22 API operations, with generated Pydantic bindings, exact monetary decoding, charge-safe retries, lazy pagination, waiters, and process-local account throttling. First preview targeting API `/v1`.
