# Changelog

## 0.1.0-rc.5 (preview)

- Add datacenter discovery, server creation and server/plan/image filters. Keep legacy location requests with a deprecation annotation.
- Validate selector requests locally and reconcile uncertain creates using the requested datacenter. Preserve absent/null datacenter responses and unknown response fields.
- Regenerate bindings from the live API snapshot with OpenAPI Generator 7.26.0.

## 0.1.0-rc.4 (preview)

Format README examples with consistent indentation and shorter lines for the npm package page. SDK runtime behavior is unchanged.

## 0.1.0-rc.3 (preview)

Add Arct Cloud website and documentation links to the package page. SDK runtime behavior is unchanged.

## 0.1.0-rc.2 (preview)

- Publish through GitHub trusted publishing with provenance.
- Keep the same SDK runtime behavior as `0.1.0-rc.1`.

## 0.1.0-rc.1 (preview)

- Cover all 22 Arct Cloud API operations with generated endpoint bindings and models.
- Add async pagination, conservative waiting, cancellation and shared local limits.
- Preserve charge uncertainty, exact resize quotes and one-time secrets.
