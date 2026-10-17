# Changelog

## 0.1.0rc3 (preview)

- Add the `arct` command and `python -m arct`, reusing the Python SDK and existing credential contexts.
- Add a repository-hosted shell installer for macOS and Linux; replace Go CLI binary distribution.

## 0.1.0rc2 (preview)

Add Arct Cloud website and documentation links to the package page. SDK runtime behavior is unchanged.

## 0.1.0rc1 (preview)

Initial Python 3.11+ sync and async SDK for all 22 API operations, with generated Pydantic bindings, exact monetary decoding, charge-safe retries, lazy pagination, waiters, and process-local account throttling. First preview targeting API `/v1`.
