import json
from pathlib import Path

import httpx
import pytest
from conftest import ACCOUNT, FIXTURES
from test_policy import ID
from test_sdk import sdk

SPEC = json.loads((Path(__file__).resolve().parents[2] / "api/openapi.json").read_text())


def sample(schema):
    if "$ref" in schema:
        key = schema["$ref"].split("/")[-1]
        if key == "Server":
            return FIXTURES["server"]
        return sample(SPEC["components"]["schemas"][key])
    if "allOf" in schema:
        return sample(schema["allOf"][0])
    if "anyOf" in schema:
        return sample(schema["anyOf"][0])
    if "enum" in schema:
        return schema["enum"][0]
    if schema.get("format") == "uuid":
        return ID
    if schema.get("format") == "date-time":
        return "2026-10-17T00:00:00Z"
    if schema.get("format") == "date":
        return "2026-10-17"
    kind = schema.get("type")
    if kind == "object":
        return {k: sample(v) for k, v in schema.get("properties", {}).items()}
    if kind == "array":
        return []
    return {"string": "example", "integer": 1, "number": 1.25, "boolean": True, "null": None}.get(kind, {})


CASES = [
    ("account", "get", (), {}, "GET", "/account", {}, None, 200),
    ("servers", "list_page", (), {"status": "running", "location": "fra", "page": 2, "per_page": 50}, "GET", "/servers", {"status": "running", "location": "fra", "page": "2", "per_page": "50"}, None, 200),
    ("servers", "create", (), {"hostname": "web-1", "location": "fra", "plan": "vm.small", "image_id": ID, "billing_period": "yearly", "ssh_key_ids": [], "coupon_code": "CODE", "enable_backups": False}, "POST", "/servers", {}, {"hostname": "web-1", "location": "fra", "plan": "vm.small", "image_id": ID, "billing_period": "yearly", "ssh_key_ids": [], "coupon_code": "CODE", "enable_backups": False}, 201),
    ("servers", "get", (ID,), {}, "GET", "/servers/" + ID, {}, None, 200),
    ("servers", "delete", (ID,), {}, "DELETE", "/servers/" + ID, {}, None, 204),
    ("servers", "update", (ID,), {"hostname": "new-host", "delete_protection": False, "labels": []}, "PATCH", "/servers/" + ID, {}, {"hostname": "new-host", "delete_protection": False, "labels": []}, 200),
    ("locations", "list_page", (), {"page": 2, "per_page": 50}, "GET", "/locations", {"page": "2", "per_page": "50"}, None, 200),
    ("plans", "list_page", (), {"location": "fra", "page": 2, "per_page": 50}, "GET", "/plans", {"location": "fra", "page": "2", "per_page": "50"}, None, 200),
    ("images", "list_page", (), {"location": "fra", "page": 2, "per_page": 50}, "GET", "/images", {"location": "fra", "page": "2", "per_page": "50"}, None, 200),
    ("invoices", "list_page", (), {"page": 2, "per_page": 50}, "GET", "/invoices", {"page": "2", "per_page": "50"}, None, 200),
    ("invoices", "get", (ID,), {}, "GET", "/invoices/" + ID, {}, None, 200),
    ("ssh_keys", "list_page", (), {"page": 2, "per_page": 50}, "GET", "/ssh-keys", {"page": "2", "per_page": "50"}, None, 200),
    ("ssh_keys", "create", (), {"name": "laptop", "public_key": "ssh-ed25519 example"}, "POST", "/ssh-keys", {}, {"name": "laptop", "public_key": "ssh-ed25519 example"}, 201),
    ("ssh_keys", "get", (ID,), {}, "GET", "/ssh-keys/" + ID, {}, None, 200),
    ("ssh_keys", "delete", (ID,), {}, "DELETE", "/ssh-keys/" + ID, {}, None, 204),
    ("servers", "start", (ID,), {}, "POST", "/servers/" + ID + "/start", {}, None, 202),
    ("servers", "stop", (ID,), {}, "POST", "/servers/" + ID + "/stop", {}, None, 202),
    ("servers", "restart", (ID,), {}, "POST", "/servers/" + ID + "/restart", {}, None, 202),
    ("servers", "reinstall", (ID,), {"image_id": ID, "ssh_key_ids": [], "hostname": "fresh"}, "POST", "/servers/" + ID + "/reinstall", {}, {"image_id": ID, "ssh_key_ids": [], "hostname": "fresh"}, 202),
    ("servers", "cancel_deletion", (ID,), {}, "POST", "/servers/" + ID + "/cancel-deletion", {}, None, 200),
    ("servers", "resize_options", (ID,), {}, "GET", "/servers/" + ID + "/resize-options", {}, None, 200),
    ("servers", "resize", (ID,), {"plan": "vm.medium", "expected_amount": "4.12"}, "POST", "/servers/" + ID + "/resize", {}, {"plan": "vm.medium", "expected_amount": "4.12"}, 202),
]

CASES += [
    ("servers", "delete", (ID,), {"at_period_end": True}, "DELETE", "/servers/" + ID, {"at_period_end": "true"}, None, 200),
    ("servers", "resize", (ID,), {"plan": "vm.medium", "expected_amount": "4.12"}, "POST", "/servers/" + ID + "/resize", {}, {"plan": "vm.medium", "expected_amount": "4.12"}, 200),
]


def handle_case(case, seen):
    resource, action, args, kwargs, method, path, query, body, status = case
    def handle(request):
        if request.url.path == "/v1/account" and path != "/account":
            return httpx.Response(200, json=ACCOUNT)
        seen.append(request)
        assert request.method == method
        assert request.url.path == "/v1" + path
        assert dict(request.url.params) == query
        assert (json.loads(request.content) if request.content else None) == body
        assert request.headers["authorization"] == "Bearer test-token"
        schema_path = next(p for p in SPEC["paths"] if p.replace("{server_id}", ID).replace("{invoice_id}", ID).replace("{key_id}", ID) == path)
        response = SPEC["paths"][schema_path][method.lower()]["responses"][str(status)]
        schema = response.get("content", {}).get("application/json", {}).get("schema")
        if schema:
            value = sample(schema)
            if action == "resize":
                value["status"] = "pending_payment" if status == 202 else "applied"
            return httpx.Response(status, json=value)
        return httpx.Response(status)
    return handle


@pytest.mark.parametrize("case", CASES, ids=["-".join(c[:2]) for c in CASES])
def test_sync_wire_operation(case):
    Arct, _ = sdk()
    seen = []
    with Arct(token="test-token", transport=httpx.MockTransport(handle_case(case, seen))) as client:
        value = getattr(getattr(client, case[0]), case[1])(*case[2], **case[3])
    assert len(seen) == 1
    assert value is not None or case[-1] == 204
    if case[1] == "resize":
        assert value.status == ("pending_payment" if case[-1] == 202 else "applied")


@pytest.mark.parametrize("case", CASES, ids=["-".join(c[:2]) for c in CASES])
async def test_async_wire_operation(case):
    _, AsyncArct = sdk()
    seen = []
    async with AsyncArct(token="test-token", transport=httpx.MockTransport(handle_case(case, seen))) as client:
        value = await getattr(getattr(client, case[0]), case[1])(*case[2], **case[3])
    assert len(seen) == 1
    assert value is not None or case[-1] == 204
    if case[1] == "resize":
        assert value.status == ("pending_payment" if case[-1] == 202 else "applied")
