import json

import httpx
import pytest
from pydantic import ValidationError

from arct import Arct, AsyncArct
from arct.models import Account, CreateServerRequest, Location, PayInvoiceRequest, Plan, ResizeOptions, Server
from conftest import ACCOUNT
from test_operations import SPEC, sample
from test_policy import ID, response
from test_sdk import created, page, server

CREATE = dict(hostname="web-1", plan="vm.small", image_id=ID)
DATACENTER = dict(code="fra1", location="fra", name="Frankfurt", region=None,
                  status="online", is_preorder=False, tiers=["vm"], future="accepted")


@pytest.mark.parametrize("placement", [{"datacenter": "Fra1"}, {"location": "fra"}, {"location": "LON1"}, {"datacenter": "fra1", "location": "FRA"}])
def test_create_placement_wire(placement):
    bodies = []
    def handle(request):
        if request.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        bodies.append(json.loads(request.content))
        return httpx.Response(201, json=created())
    with Arct(token="token", transport=httpx.MockTransport(handle)) as client:
        client.servers.create(**CREATE, **placement)
    assert bodies == [CREATE | placement]


@pytest.mark.parametrize("placement", [{}, {"datacenter": "fra"}, {"datacenter": "fra123"}, {"datacenter": "a1"}, {"datacenter": "abcdef1"}, {"datacenter": "fra-1"}, {"datacenter": "fra1\n"}, {"datacenter": 1}, {"datacenter": None}, {"location": None}, {"datacenter": "fra1", "location": "bad!"}])
def test_invalid_placement_is_local(placement):
    with Arct(token="token", transport=httpx.MockTransport(lambda r: pytest.fail("No request expected"))) as client:
        with pytest.raises(ValidationError):
            client.servers.create(**CREATE, **placement)


def test_request_validation_remains_strict():
    for fields in ({"hostname": "bad!"}, {"plan": "bad!"}, {"image_id": "bad"}, {"enable_backups": "true"}, {"unexpected": True}, {"ssh_key_ids": None}):
        with pytest.raises(ValidationError):
            CreateServerRequest.model_validate(CREATE | {"datacenter": "fra1"} | fields)


@pytest.mark.parametrize("resource", ["servers", "plans", "images"])
def test_datacenter_filters_and_validation(resource):
    queries = []
    def handle(request):
        queries.append(dict(request.url.params))
        return httpx.Response(200, json=page([], 1))
    with Arct(token="token", transport=httpx.MockTransport(handle)) as client:
        assert list(getattr(client, resource).list(datacenter="FRA1")) == []
        with pytest.raises(ValidationError):
            list(getattr(client, resource).list(datacenter="fra"))
    assert queries == [{"page": "1", "per_page": "100", "datacenter": "FRA1"}]


def test_datacenters_and_legacy_warnings():
    with Arct(token="token", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=page([DATACENTER]) if r.url.path.endswith("/datacenters") else page([])))) as client:
        assert list(client.datacenters.list())[0].future == "accepted"
        assert list(client.locations.list()) == []
        for resource in (client.servers, client.images, client.plans):
            with pytest.warns(DeprecationWarning, match="location"):
                list(resource.list(location="fra"))
    with Arct(token="token", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=ACCOUNT) if r.url.path.endswith("/account") else httpx.Response(201, json=created()))) as client:
        with pytest.warns(DeprecationWarning, match="location"):
            client.servers.create(**CREATE, location="fra")


async def test_async_datacenters_create_and_filters():
    seen = []
    def handle(request):
        seen.append(request)
        if request.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        if request.method == "POST":
            return httpx.Response(201, json=created())
        return httpx.Response(200, json=page([DATACENTER]) if request.url.path.endswith("/datacenters") else page([]))
    async with AsyncArct(token="token", transport=httpx.MockTransport(handle)) as client:
        assert [v.code async for v in client.datacenters.list()] == ["fra1"]
        await client.servers.create(**CREATE, datacenter="fra1")
        for resource in (client.servers, client.images, client.plans):
            assert [v async for v in resource.list(datacenter="fra1")] == []
        assert [v async for v in client.locations.list()] == []
    assert json.loads(next(r.content for r in seen if r.method == "POST")) == CREATE | {"datacenter": "fra1"}


@pytest.mark.parametrize("model,field", [(Location, "datacenters"), (Plan, "datacenters"), (Server, "datacenter")])
@pytest.mark.parametrize("state", ["absent", "null", "present"])
def test_additive_response_fields(model, field, state):
    value = sample(SPEC["components"]["schemas"][model.__name__])
    value.pop(field, None)
    if state != "absent":
        value[field] = None if state == "null" else "fra1" if field == "datacenter" else ["fra1"]
    value["future"] = {"field": True}
    result = model.model_validate(value)
    assert getattr(result, field) == value.get(field)
    assert result.future == {"field": True}


@pytest.mark.parametrize("model,fields", [(Account, ["credit_balance", "credit_autopay"]), (ResizeOptions, ["credit_balance", "payment_methods"])])
def test_additive_credit_response_fields(model, fields):
    value = sample(SPEC["components"]["schemas"][model.__name__])
    for field in fields:
        value.pop(field, None)
    result = model.model_validate(value)
    assert all(getattr(result, field) is None for field in fields)
    for field in fields:
        with pytest.raises(ValidationError):
            model.model_validate(value | {field: None})


def test_invoice_payment_const_remains_strict():
    assert PayInvoiceRequest(payment_method="credit").payment_method == "credit"
    for value in ("card", "other", 1, None):
        with pytest.raises(ValidationError):
            PayInvoiceRequest(payment_method=value)


@pytest.mark.parametrize("placement,datacenter,location,match", [
    ({"datacenter": "FRA1"}, "fra1", "fra", True),
    ({"datacenter": "fra1"}, None, "fra", False),
    ({"datacenter": "fra1"}, "fra2", "fra", False),
    ({"location": "FRA"}, None, "fra", True),
    ({"location": "LON1"}, "lon1", "lon", True),
    ({"location": "lon1"}, None, "lon", False),
    ({"datacenter": "fra1", "location": "lon"}, "fra1", "fra", False),
])
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_reconciliation_placement_stays_uncertain(monkeypatch, placement, datacenter, location, match, asynchronous):
    from arct._transport import Transport
    from arct.errors import UncertainOperationError
    monkeypatch.setattr(Transport, "sleep", lambda *a: None)
    async def asleep(*args):
        pass
    monkeypatch.setattr(Transport, "asleep", asleep)
    attempts = []
    candidate = server()
    candidate.update(datacenter=datacenter, location=location)
    def handle(request):
        if request.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        if request.method == "GET":
            return httpx.Response(200, json=page([candidate]))
        attempts.append(request.content)
        return response(503 if len(attempts) == 1 else 409, "unavailable" if len(attempts) == 1 else "hostname_taken")
    client = (AsyncArct if asynchronous else Arct)(token="token", transport=httpx.MockTransport(handle))
    try:
        with pytest.raises(UncertainOperationError) as error:
            if asynchronous:
                await client.servers.create(**CREATE, **placement)
            else:
                client.servers.create(**CREATE, **placement)
        assert error.value.details["candidate_checks"][0]["attributes_match"] is match
        assert len(attempts) == 2 and attempts[0] == attempts[1]
    finally:
        if asynchronous:
            await client.aclose()
        else:
            client.close()
