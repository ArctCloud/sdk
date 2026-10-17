import asyncio
from decimal import Decimal
import json
import time

import httpx
import pytest
from conftest import ACCOUNT, FIXTURES
from test_sdk import created, order, page, sdk, server

ID = "00000000-0000-0000-0000-000000000001"
CREATE = dict(hostname="web-1", location="fra", plan="vm.small", image_id=ID)


def response(status=500, code="unavailable", details=None, headers=None):
    return httpx.Response(status, json={"error": {"code": code, "message": "Failure", "details": details}}, headers=headers)


def test_charge_unknown_priority_and_attempt_count(monkeypatch):
    from arct.errors import ChargeUnknownError
    Arct, _ = sdk()
    attempts = []
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        attempts.append(r)
        return response(503, details={"order_intent_id": "support-123"})
    with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
        with pytest.raises(ChargeUnknownError) as error:
            c.servers.create(**CREATE)
        assert error.value.details["order_intent_id"] == "support-123"
        assert len(attempts) == 1


@pytest.mark.parametrize("failure", ["network", "500", "503", "429", "promo_changed"])
def test_create_retries_identical_body(monkeypatch, failure):
    from arct._transport import Transport
    Arct, _ = sdk()
    monkeypatch.setattr(Transport, "sleep", lambda *a: None)
    bodies = []
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        bodies.append(r.content)
        if len(bodies) < (2 if failure == "promo_changed" else 3):
            if failure == "network":
                raise httpx.ReadError("private-token", request=r)
            return response(409 if failure == "promo_changed" else int(failure), failure, headers={"Retry-After": "0"})
        return httpx.Response(201, json=created())
    with Arct(token="private-token", transport=httpx.MockTransport(handle)) as c:
        assert c.servers.create(**CREATE).order.order_number == "ORD-1"
    assert len(bodies) == (2 if failure == "promo_changed" else 3)
    assert len(set(bodies)) == 1


def test_hostname_reconciliation_is_uncertain(monkeypatch):
    from arct._transport import Transport
    from arct.errors import UncertainOperationError
    Arct, _ = sdk()
    monkeypatch.setattr(Transport, "sleep", lambda *a: None)
    attempts = []
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        if r.method == "GET":
            return httpx.Response(200, json=page([server()]))
        attempts.append(r)
        return response(503 if len(attempts) == 1 else 409, "unavailable" if len(attempts) == 1 else "hostname_taken")
    with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
        with pytest.raises(UncertainOperationError) as error:
            c.servers.create(**CREATE)
        assert len(error.value.candidates) == 1
        assert len(attempts) == 2
        assert not hasattr(error.value, "order")


@pytest.mark.parametrize("method,fields", [("restart", {}), ("reinstall", {"image_id": ID}), ("delete", {}), ("resize", {"plan": "vm.medium", "expected_amount": Decimal("4.12")})])
def test_other_mutations_do_not_retry_lost_responses(method, fields):
    from arct.errors import UncertainOperationError
    Arct, _ = sdk()
    attempts = []
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        attempts.append(r)
        raise httpx.ReadError("one-time-secret", request=r)
    with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
        with pytest.raises(UncertainOperationError):
            getattr(c.servers, method)(ID, **fields)
    assert len(attempts) == 1


@pytest.mark.parametrize("case", FIXTURES["documented_errors"])
def test_documented_errors(case, monkeypatch):
    from arct._transport import Transport
    from arct.errors import APIError, ChargeUnknownError
    Arct, _ = sdk()
    monkeypatch.setattr(Transport, "sleep", lambda *a: None)
    with Arct(token="token", transport=httpx.MockTransport(lambda r: httpx.Response(case["status"], json=case["body"]))) as c:
        with pytest.raises(APIError) as error:
            c.servers.get(ID)
    assert error.value.status == case["status"]
    assert error.value.code == case["body"]["error"]["code"]
    if case["body"]["error"]["code"] == "payment_pending":
        assert isinstance(error.value, ChargeUnknownError)


def test_resize_uses_exact_quote_and_preserves_explicit_amount():
    Arct, _ = sdk()
    sent = []
    quote = dict(can_resize=True, blocked_code=None, blocked_reason=None, current_plan="vm.small", billing_period="monthly", current_price_period=1, period_end=None, days_left=None, card=None, promo=None, unpaid_invoice=None, pending_resize=None, plans=[dict(slug="vm.medium", name="Medium", cpu_cores=2, ram_gb=2, storage_gb=20, bandwidth_tb=1, price_period=2, price_period_list=2, promo_applies=False, is_current=False, eligible=True, reason=None, reason_label=None, amount_due_today="4.1234567890123456789")])
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        if r.method == "GET":
            return httpx.Response(200, json=quote)
        sent.append(json.loads(r.content))
        return response(409, "price_changed")
    from arct.errors import ConflictError
    with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
        with pytest.raises(ConflictError):
            c.servers.resize(ID, plan="vm.medium")
        with pytest.raises(ConflictError):
            c.servers.resize(ID, plan="vm.medium", expected_amount=Decimal("4.12"))
    assert sent == [{"plan": "vm.medium", "expected_amount": "4.1234567890123456789"}, {"plan": "vm.medium", "expected_amount": "4.12"}]


async def test_async_retry_is_cancellable():
    _, AsyncArct = sdk()
    entered = asyncio.Event()
    async def handle(r):
        entered.set()
        return response(429, "rate_limit_exceeded", headers={"Retry-After": "60"})
    async with AsyncArct(token="token", transport=httpx.MockTransport(handle)) as c:
        task = asyncio.create_task(c.servers.get(ID))
        await entered.wait()
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


def test_wait_preserves_password_and_requires_restart_transition(monkeypatch):
    from arct.errors import WaitTimeoutError
    Arct, _ = sdk()
    now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    monkeypatch.setattr(time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    observations = []
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        if r.method == "POST":
            return httpx.Response(201 if r.url.path.endswith("/servers") else 202, json=created() if r.url.path.endswith("/servers") else server())
        observations.append(r)
        return httpx.Response(200, json=server())
    with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
        result = c.servers.create(**CREATE)
        assert c.servers.wait_until(result, "running").status == "running"
        assert result.password.get_secret_value() == "one-time-secret"
        restart = c.servers.restart(ID)
        with pytest.raises(WaitTimeoutError):
            c.servers.wait_until(restart, "running", timeout=0.01)
        assert len(observations) >= 2


def test_wait_deadline_and_terminal_state(monkeypatch):
    from arct.errors import OperationFailedError, WaitTimeoutError
    Arct, _ = sdk()
    now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    monkeypatch.setattr(time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    value = server()
    value["status"] = "error"
    with Arct(token="token", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=value))) as c:
        with pytest.raises(OperationFailedError) as error:
            c.servers.wait_until(ID, "running")
        assert error.value.last_state.status == "error"
    value["status"] = "pre_order"
    with Arct(token="other", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=value))) as c:
        before = time.monotonic()
        with pytest.raises(WaitTimeoutError) as error:
            c.servers.wait_until(ID, "running", timeout=0.01)
        assert time.monotonic() - before == pytest.approx(0.01)
        assert error.value.last_state.status == "pre_order"
