import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import time

import httpx
import pytest
from conftest import ACCOUNT, FIXTURES
from test_policy import CREATE, ID, response
from test_sdk import created, page, sdk, server


def test_token_env_and_local_validation(monkeypatch):
    Arct, _ = sdk()
    monkeypatch.delenv("ARCT_TOKEN", raising=False)
    with pytest.raises(ValueError):
        Arct()
    monkeypatch.setenv("ARCT_TOKEN", "environment-token")
    with Arct(token="explicit-token", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=server()))) as c:
        assert c.servers.get(ID).hostname == "web-1"
        for kwargs in ({"status": "error"}, {"per_page": 101}, {"page": 0}):
            with pytest.raises(ValueError):
                c.servers.list_page(**kwargs)
        with pytest.raises(ValueError):
            c.servers.get("../../other")
    for url in ("http://example.com", "https://user:secret@example.com", "https://example.com?token=x"):
        with pytest.raises(ValueError):
            Arct(base_url=url)
    for timeout in (0, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            Arct(timeout=timeout)
    with Arct(base_url="http://localhost:9000/v1", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=server()))):
        pass


def test_redirect_does_not_forward_auth():
    from arct.errors import APIError
    Arct, _ = sdk()
    requests = []
    def handle(r):
        requests.append(r)
        return httpx.Response(307, headers={"Location": "https://evil.example/collect"})
    with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
        with pytest.raises(APIError):
            c.servers.get(ID)
    assert len(requests) == 1


def test_error_redaction_validation_and_non_json():
    from arct.errors import APIError, ValidationError
    Arct, _ = sdk()
    case = FIXTURES["validation_error"]
    body = case["body"] if "body" in case else case
    with Arct(token="arct_abcdefsecret", transport=httpx.MockTransport(lambda r: httpx.Response(422, json=body))) as c:
        with pytest.raises(ValidationError) as error:
            c.servers.get(ID)
        assert error.value.fields
    with Arct(token="arct_abcdefsecret", transport=httpx.MockTransport(lambda r: httpx.Response(502, text="arct_abcdefsecret password=hidden"))) as c:
        with pytest.raises(APIError) as error:
            c.servers.get(ID)
        assert "abcdefsecret" not in repr(error.value) + str(error.value)
    body = {"error": {"code": "new_error", "message": "arct_abcdefsecret", "details": {"password": "one-time", "Authorization": "Bearer arct_abcdefsecret", "order_id": "support"}}}
    with Arct(token="arct_abcdefsecret", transport=httpx.MockTransport(lambda r: httpx.Response(400, json=body))) as c:
        with pytest.raises(APIError) as error:
            c.servers.get(ID)
        assert error.value.details["order_id"] == "support"
        assert "one-time" not in str(error.value.details)
        assert "abcdefsecret" not in str(error.value)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_exact_attempt_limit_for_reads(asynchronous, monkeypatch):
    from arct._transport import Transport
    from arct.errors import APIError
    Arct, AsyncArct = sdk()
    count = []
    def handle(r):
        count.append(r)
        return response(500)
    monkeypatch.setattr(Transport, "sleep", lambda *a: None)
    async def no_sleep(*args):
        pass
    monkeypatch.setattr(Transport, "asleep", no_sleep)
    if asynchronous:
        async def run():
            async with AsyncArct(token="token", transport=httpx.MockTransport(handle)) as c:
                with pytest.raises(APIError):
                    await c.servers.get(ID)
        asyncio.run(run())
    else:
        with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
            with pytest.raises(APIError):
                c.servers.get(ID)
    assert len(count) == 3


async def test_account_limits_shared_across_tokens_and_sync_async(monkeypatch):
    from arct import _limits
    from arct._transport import Transport
    Arct, AsyncArct = sdk()
    now = [10000.0]
    monkeypatch.setattr(_limits.time, "monotonic", lambda: now[0])
    sleeps = []
    async def sleep(self, delay, deadline):
        sleeps.append(delay)
        now[0] += delay
        await asyncio.sleep(0)
    monkeypatch.setattr(Transport, "asleep", sleep)
    def handle(r):
        return httpx.Response(200 if r.method == "GET" else 201, json=ACCOUNT if r.url.path.endswith("/account") else created())
    with Arct(token="first", transport=httpx.MockTransport(handle)) as c:
        for _ in range(5):
            c.servers.create(**CREATE)
    async with AsyncArct(token="second", transport=httpx.MockTransport(handle)) as c:
        await c.servers.create(**CREATE)
    assert sleeps == [60.0]


async def test_paid_hour_limit_and_cancelled_throttle():
    from arct import _limits
    _, AsyncArct = sdk()
    token = _limits.token_key("token")
    _limits.bind(token, ACCOUNT["id"])
    now = time.monotonic()
    _limits._EVENTS[("account", ACCOUNT["id"], "paid_hour")] = deque([now - 120] * 20)
    sent = []
    async with AsyncArct(token="token", transport=httpx.MockTransport(lambda r: sent.append(r))) as c:
        task = asyncio.create_task(c.servers.create(**CREATE))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert not sent


async def test_async_wait_is_cancellable_and_deadline_bounded():
    from arct.errors import WaitTimeoutError
    _, AsyncArct = sdk()
    value = server()
    value["status"] = "provisioning"
    calls = []
    async def handle(r):
        calls.append(r)
        return httpx.Response(200, json=value)
    async with AsyncArct(token="token", transport=httpx.MockTransport(handle)) as c:
        task = asyncio.create_task(c.servers.wait_until(ID, "running"))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(calls) == 1
        with pytest.raises(WaitTimeoutError) as error:
            await c.servers.wait_until(ID, "running", timeout=0.01)
        assert error.value.last_state.status == "provisioning"


def test_acknowledged_delayed_create_discovers_by_hostname():
    Arct, _ = sdk()
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        if r.method == "POST":
            result = created()
            result["server"] = None
            return httpx.Response(201, json=result)
        if r.url.path.endswith("/servers"):
            return httpx.Response(200, json=page([server()]))
        return httpx.Response(200, json=server())
    with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
        result = c.servers.create(**CREATE)
        assert c.servers.wait_until(result, "running").hostname == "web-1"
        assert result.server is None


def test_restart_transition_and_reinstall_password_preserved(monkeypatch):
    from arct._transport import Transport
    Arct, _ = sdk()
    monkeypatch.setattr(Transport, "sleep", lambda *args: None)
    statuses = iter(["running", "reinstalling", "running"])
    calls = []
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        if r.method == "POST":
            return httpx.Response(202, json=dict(server=server(), password="one-time-secret"))
        value = server()
        value["status"] = next(statuses)
        calls.append(r)
        return httpx.Response(200, json=value)
    with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
        result = c.servers.reinstall(ID, image_id=ID)
        assert c.servers.wait_until(result, "running").status == "running"
        assert len(calls) == 3
        assert result.password.get_secret_value() == "one-time-secret"


def test_retry_after_deadline_caps_wait(monkeypatch):
    from arct.errors import WaitTimeoutError
    Arct, _ = sdk()
    now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    monkeypatch.setattr(time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    calls = []
    def handle(r):
        calls.append(r)
        return response(429, headers={"Retry-After": "600"})
    before = time.monotonic()
    with Arct(token="token", operation_timeout=0.01, transport=httpx.MockTransport(handle)) as c:
        with pytest.raises(WaitTimeoutError):
            c.servers.get(ID)
    assert time.monotonic() - before == pytest.approx(0.01)
    assert len(calls) == 1


def test_retried_hostname_charge_marker_wins_over_reconciliation(monkeypatch):
    from arct.errors import ChargeUnknownError
    from arct._transport import Transport
    Arct, _ = sdk()
    monkeypatch.setattr(Transport, "sleep", lambda *a: None)
    mutations = []
    discovery = []
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        if r.method == "GET":
            discovery.append(r)
            return httpx.Response(200, json=page([server()]))
        mutations.append(r)
        return response(503) if len(mutations) == 1 else response(409, "hostname_taken", {"order_intent_id": "support-id"})
    with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
        with pytest.raises(ChargeUnknownError):
            c.servers.create(**CREATE)
    assert len(mutations) == 2
    assert not discovery


async def test_async_http_operation_deadline_is_typed():
    from arct.errors import WaitTimeoutError
    _, AsyncArct = sdk()
    async def handle(r):
        await asyncio.sleep(60)
    async with AsyncArct(token="token", operation_timeout=0.01, transport=httpx.MockTransport(handle)) as c:
        with pytest.raises(WaitTimeoutError):
            await c.servers.get(ID)


def test_reinstall_server_reference_keeps_transition_requirement(monkeypatch):
    from arct._transport import Transport
    from arct.errors import WaitTimeoutError
    Arct, _ = sdk()
    monkeypatch.setattr(Transport, "sleep", lambda *a: None)
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        return httpx.Response(202, json=dict(server=server(), password="one-time")) if r.method == "POST" else httpx.Response(200, json=server())
    with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
        value = c.servers.reinstall(ID, image_id=ID)
        with pytest.raises(WaitTimeoutError):
            c.servers.wait_until(value.server, "running", timeout=0.01)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_ambiguous_create_discovery_uses_known_id(asynchronous, monkeypatch):
    from arct._transport import Transport
    from arct.errors import UncertainOperationError
    Arct, AsyncArct = sdk()
    monkeypatch.setattr(Transport, "sleep", lambda *a: None)
    async def no_sleep(*args):
        pass
    monkeypatch.setattr(Transport, "asleep", no_sleep)
    paths = []
    mutations = []
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        if r.method == "GET":
            paths.append(r.url.path)
            return httpx.Response(200, json=server()) if r.url.path.endswith(ID) else httpx.Response(200, json=page([server()]))
        mutations.append(r)
        return response(503) if len(mutations) == 1 else response(409, "hostname_taken", {"server_id": ID})
    if asynchronous:
        async def run():
            async with AsyncArct(token="token", transport=httpx.MockTransport(handle)) as c:
                with pytest.raises(UncertainOperationError) as error:
                    await c.servers.create(**CREATE)
                assert error.value.candidates[0].hostname == "web-1"
        asyncio.run(run())
    else:
        with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
            with pytest.raises(UncertainOperationError) as error:
                c.servers.create(**CREATE)
            assert error.value.candidates[0].hostname == "web-1"
    assert paths == ["/v1/servers/" + ID]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_resize_wait_requires_options_and_server_plan(asynchronous, monkeypatch):
    from arct._transport import Transport
    from arct.models import ResizeResponse
    from test_operations import sample, SPEC
    Arct, AsyncArct = sdk()
    monkeypatch.setattr(Transport, "sleep", lambda *a: None)
    async def no_sleep(*args):
        pass
    monkeypatch.setattr(Transport, "asleep", no_sleep)
    options = sample(SPEC["components"]["schemas"]["ResizeOptions"])
    options.update(current_plan="vm.medium", pending_resize=None)
    result = ResizeResponse.model_validate(dict(status="pending_payment", resize_id=ID, invoice_id=ID, invoice_number="INV-1", amount="4.12", to_plan="vm.medium", restart_required=True))
    gets = []
    def handle(r):
        assert r.method == "GET"
        if r.url.path.endswith("resize-options"):
            return httpx.Response(200, json=options)
        gets.append(r)
        value = server()
        value["plan"] = "vm.small" if len(gets) == 1 else "vm.medium"
        return httpx.Response(200, json=value)
    if asynchronous:
        async def run():
            async with AsyncArct(token="token", transport=httpx.MockTransport(handle)) as c:
                assert (await c.servers.wait_resize(ID, result)).plan == "vm.medium"
        asyncio.run(run())
    else:
        with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
            assert c.servers.wait_resize(ID, result).plan == "vm.medium"
    assert len(gets) == 2


async def test_async_create_retries_and_secrets(monkeypatch):
    from arct._transport import Transport
    from arct.errors import ChargeUnknownError
    _, AsyncArct = sdk()
    waits = []
    async def sleep(self, delay, deadline):
        waits.append(delay)
        await asyncio.sleep(0)
    monkeypatch.setattr(Transport, "asleep", sleep)
    bodies = []
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        bodies.append(r.content)
        return response(500) if len(bodies) < 3 else httpx.Response(201, json=created())
    async with AsyncArct(token="token", transport=httpx.MockTransport(handle)) as c:
        result = await c.servers.create(**CREATE)
        assert result.password.get_secret_value() == "one-time-secret"
    assert len(bodies) == 3 and len(set(bodies)) == 1 and len(waits) == 2
    calls = []
    def charge(r):
        calls.append(r)
        return response(429, details={"order_intent_id": "charge"})
    async with AsyncArct(token="token", transport=httpx.MockTransport(charge)) as c:
        with pytest.raises(ChargeUnknownError):
            await c.servers.create(**CREATE)
    assert len(calls) == 1


def test_ambiguous_candidates_compare_attributes_and_creation_time(monkeypatch):
    from arct._transport import Transport
    from arct.errors import UncertainOperationError
    Arct, _ = sdk()
    monkeypatch.setattr(Transport, "sleep", lambda *a: None)
    attempts = []
    candidates = [server(), server()]
    candidates[0]["created_at"] = "2000-01-01T00:00:00Z"
    candidates[1].update(location="nyc", plan="vm.large", created_at="2099-01-01T00:00:00Z")
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        if r.method == "GET":
            return httpx.Response(200, json=page(candidates))
        attempts.append(r)
        return response(503) if len(attempts) == 1 else response(409, "hostname_taken")
    with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
        with pytest.raises(UncertainOperationError) as error:
            c.servers.create(**CREATE)
    assert error.value.details["candidate_checks"] == [
        {"server_id": ID, "attributes_match": True, "created_since_attempt": False},
        {"server_id": ID, "attributes_match": False, "created_since_attempt": True},
    ]


@pytest.mark.parametrize("asynchronous", [False, True])
def test_reconciliation_read_failure_remains_creation_uncertainty(asynchronous, monkeypatch):
    from arct._transport import Transport
    from arct.errors import UncertainOperationError
    Arct, AsyncArct = sdk()
    monkeypatch.setattr(Transport, "sleep", lambda *a: None)
    async def no_sleep(*args):
        pass
    monkeypatch.setattr(Transport, "asleep", no_sleep)
    attempts = []
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        if r.method == "GET":
            return response(403, "insufficient_scope")
        attempts.append(r)
        return response(503) if len(attempts) == 1 else response(409, "hostname_taken")
    if asynchronous:
        async def run():
            async with AsyncArct(token="token", transport=httpx.MockTransport(handle)) as c:
                with pytest.raises(UncertainOperationError):
                    await c.servers.create(**CREATE)
        asyncio.run(run())
    else:
        with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
            with pytest.raises(UncertainOperationError):
                c.servers.create(**CREATE)
    assert len(attempts) == 2


def test_shared_decimal_wire_fixture_with_respx():
    from decimal import Decimal
    import respx
    Arct, _ = sdk()
    values = json.loads(FIXTURES["money_json"], parse_float=Decimal)
    payload = created()
    payload["order"]["amount"] = "AMOUNT_PLACEHOLDER"
    payload["server"]["price"] = "PRICE_PLACEHOLDER"
    raw = json.dumps(payload).replace('"AMOUNT_PLACEHOLDER"', str(values["amount"])).replace('"PRICE_PLACEHOLDER"', str(values["price"]))
    with respx.mock:
        respx.get("https://api.arct.cloud/v1/account").mock(return_value=httpx.Response(200, json=ACCOUNT))
        respx.post("https://api.arct.cloud/v1/servers").mock(return_value=httpx.Response(201, content=raw))
        with Arct(token="arct_testtoken") as c:
            result = c.servers.create(**CREATE)
            assert result.order.amount == Decimal("1234567890.123456789")
            assert result.server.price == Decimal("0.1")


@pytest.mark.parametrize("case", FIXTURES["documented_errors"])
async def test_async_documented_errors_with_respx(case, monkeypatch):
    import respx
    from arct._transport import Transport
    from arct.errors import APIError
    _, AsyncArct = sdk()
    async def no_sleep(*args):
        pass
    monkeypatch.setattr(Transport, "asleep", no_sleep)
    with respx.mock:
        respx.get("https://api.arct.cloud/v1/servers/" + ID).mock(return_value=httpx.Response(case["status"], json=case["body"]))
        async with AsyncArct(token="arct_testtoken") as c:
            with pytest.raises(APIError) as error:
                await c.servers.get(ID)
        assert error.value.status == case["status"]
        assert error.value.code == case["body"]["error"]["code"]


@pytest.mark.parametrize("token", [1, "x\ny", "x\ry", "x y", "😀"])
def test_invalid_token_fails_locally(token):
    Arct, _ = sdk()
    with pytest.raises(ValueError):
        Arct(token=token)


def test_resize_quote_and_mutation_share_operation_deadline(monkeypatch):
    from arct._transport import Transport
    from arct.errors import WaitTimeoutError
    from test_operations import SPEC, sample
    Arct, _ = sdk()
    now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    monkeypatch.setattr(time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    options = sample(SPEC["components"]["schemas"]["ResizeOptions"])
    selected = sample(SPEC["components"]["schemas"]["ResizePlan"])
    selected.update(slug="vm.medium", eligible=True, amount_due_today="4.12")
    options.update(can_resize=True, plans=[selected])
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        if r.method == "GET":
            now[0] += 0.008
            return httpx.Response(200, json=options)
        return response(429, headers={"Retry-After": "60"})
    with Arct(token="token", operation_timeout=0.01, transport=httpx.MockTransport(handle)) as c:
        with pytest.raises(WaitTimeoutError):
            c.servers.resize(ID, plan="vm.medium")
    assert now[0] - 1000 < 0.011


def test_create_retry_deadline_keeps_uncertain_outcome(monkeypatch):
    from arct.errors import UncertainOperationError
    Arct, _ = sdk()
    now = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    monkeypatch.setattr(time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    calls = []
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        calls.append(r)
        return response(503)
    with Arct(token="token", operation_timeout=0.01, transport=httpx.MockTransport(handle)) as c:
        with pytest.raises(UncertainOperationError) as error:
            c.servers.create(**CREATE)
    assert len(calls) == 1
    assert error.value.details["deadline_exceeded"] is True


async def test_async_dispatched_mutation_deadline_keeps_uncertainty():
    from arct.errors import UncertainOperationError
    _, AsyncArct = sdk()
    calls = []
    async def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        calls.append(r)
        await asyncio.sleep(60)
    async with AsyncArct(token="token", operation_timeout=0.01, transport=httpx.MockTransport(handle)) as c:
        with pytest.raises(UncertainOperationError):
            await c.servers.restart(ID)
    assert len(calls) == 1


def test_empty_success_body_is_a_usable_error():
    from arct.errors import APIError, UncertainOperationError
    Arct, _ = sdk()
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        return httpx.Response(201 if r.method == "POST" else 200)
    with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
        with pytest.raises(APIError) as error:
            c.servers.get(ID)
        assert error.value.code == "invalid_response"
        with pytest.raises(UncertainOperationError):
            c.servers.create(**CREATE)


def test_password_and_token_do_not_enter_logs(caplog):
    import logging
    Arct, _ = sdk()
    caplog.set_level(logging.DEBUG)
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        return httpx.Response(201, json=created())
    with Arct(token="arct_private_testtoken", transport=httpx.MockTransport(handle)) as c:
        result = c.servers.create(**CREATE)
        representations = repr(c) + repr(c._transport) + repr(result) + result.model_dump_json()
    assert "one-time-secret" not in caplog.text + representations
    assert "arct_private_testtoken" not in caplog.text + representations


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("compressed", [False, True])
def test_streaming_response_cannot_succeed_past_deadline(asynchronous, compressed):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from arct.errors import WaitTimeoutError
    Arct, AsyncArct = sdk()
    raw = json.dumps(server()).encode()
    if compressed:
        import gzip
        raw = gzip.compress(raw, mtime=0)
        raw = raw[:3] + b"\x08" + raw[4:10] + b"x" * 1600 + b"\x00" + raw[10:]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            if compressed:
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                for offset in range(0, len(raw), 80):
                    self.wfile.write(raw[offset:offset + 80])
                    self.wfile.flush()
                    time.sleep(0.015)
            except (BrokenPipeError, ConnectionResetError):
                pass
    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{http.server_port}/v1"
    elapsed = []
    try:
        if asynchronous:
            async def run():
                async with AsyncArct(token="token", base_url=url, operation_timeout=0.04) as c:
                    started = time.monotonic()
                    with pytest.raises(WaitTimeoutError):
                        await c.servers.wait_until(ID, "running", timeout=0.04)
                    elapsed.append(time.monotonic() - started)
            asyncio.run(run())
        else:
            with Arct(token="token", base_url=url, operation_timeout=0.04) as c:
                started = time.monotonic()
                with pytest.raises(WaitTimeoutError):
                    c.servers.wait_until(ID, "running", timeout=0.04)
                elapsed.append(time.monotonic() - started)
        assert elapsed[0] < 0.12
    finally:
        http.shutdown()
        http.server_close()
        thread.join()


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("mutation", [False, True])
def test_decoding_error_is_typed_and_never_replays_mutation(asynchronous, mutation):
    from arct.errors import APIError, UncertainOperationError
    Arct, AsyncArct = sdk()
    calls = []
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        calls.append(r)
        return httpx.Response(201 if mutation else 200, headers={"Content-Encoding": "gzip"}, content=b"invalid-gzip")
    kind = UncertainOperationError if mutation else APIError
    if asynchronous:
        async def run():
            async with AsyncArct(token="token", transport=httpx.MockTransport(handle)) as c:
                with pytest.raises(kind):
                    await c.servers.create(**CREATE) if mutation else await c.servers.get(ID)
        asyncio.run(run())
    else:
        with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
            with pytest.raises(kind):
                c.servers.create(**CREATE) if mutation else c.servers.get(ID)
    assert len(calls) == 1


async def test_async_empty_success_body_is_a_usable_error():
    from arct.errors import APIError, UncertainOperationError
    _, AsyncArct = sdk()
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        return httpx.Response(201 if r.method == "POST" else 200)
    async with AsyncArct(token="token", transport=httpx.MockTransport(handle)) as c:
        with pytest.raises(APIError) as error:
            await c.servers.get(ID)
        assert error.value.code == "invalid_response"
        with pytest.raises(UncertainOperationError):
            await c.servers.create(**CREATE)


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("preloaded", [False, True])
def test_valid_gzip_responses_decode_once(asynchronous, preloaded):
    import gzip
    Arct, AsyncArct = sdk()
    raw = gzip.compress(json.dumps(server()).encode(), mtime=0)
    class SyncBody(httpx.SyncByteStream):
        def __iter__(self):
            for offset in range(0, len(raw), 11):
                yield raw[offset:offset + 11]
    class AsyncBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            for offset in range(0, len(raw), 11):
                await asyncio.sleep(0)
                yield raw[offset:offset + 11]
    def handle(r):
        headers = {"Content-Type": "application/json", "Content-Encoding": "gzip"}
        if preloaded:
            return httpx.Response(200, headers=headers, content=raw)
        return httpx.Response(200, headers=headers, stream=AsyncBody() if asynchronous else SyncBody())
    if asynchronous:
        async def run():
            async with AsyncArct(token="token", transport=httpx.MockTransport(handle)) as c:
                assert (await c.servers.get(ID)).hostname == "web-1"
        asyncio.run(run())
    else:
        with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
            assert c.servers.get(ID).hostname == "web-1"


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("mutation", [False, True])
def test_unexpected_204_is_typed_not_false_success(asynchronous, mutation):
    from arct.errors import APIError, UncertainOperationError
    Arct, AsyncArct = sdk()
    calls = []
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        calls.append(r)
        return httpx.Response(204)
    kind = UncertainOperationError if mutation else APIError
    if asynchronous:
        async def run():
            async with AsyncArct(token="token", transport=httpx.MockTransport(handle)) as c:
                with pytest.raises(kind) as error:
                    await c.servers.create(**CREATE) if mutation else await c.servers.get(ID)
                assert error.value.status == 204
        asyncio.run(run())
    else:
        with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
            with pytest.raises(kind) as error:
                c.servers.create(**CREATE) if mutation else c.servers.get(ID)
            assert error.value.status == 204
    assert len(calls) == 1


def test_delete_return_type_includes_documented_empty_result():
    from typing import get_type_hints, get_args
    from arct._generated.api.servers_api import ServersApi, AsyncServersApi
    from arct.models import Server
    for cls in (ServersApi, AsyncServersApi):
        annotation = get_type_hints(cls.delete)["return"]
        assert set(get_args(annotation)) == {Server, type(None)}


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("resource,scheduled", [("servers", None), ("servers", False), ("servers", True), ("ssh_keys", None)])
def test_bodyless_delete_preserves_requested_mode(asynchronous, resource, scheduled):
    from arct.errors import UncertainOperationError
    Arct, AsyncArct = sdk()
    calls = []
    def handle(request):
        if request.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        calls.append(request)
        return httpx.Response(204)
    kwargs = {} if scheduled is None else {"at_period_end": scheduled}
    if asynchronous:
        async def run():
            async with AsyncArct(token="delete-mode", transport=httpx.MockTransport(handle)) as client:
                if scheduled is True:
                    with pytest.raises(UncertainOperationError) as error:
                        await getattr(client, resource).delete(ID, **kwargs)
                    assert error.value.status == 204
                else:
                    assert await getattr(client, resource).delete(ID, **kwargs) is None
        asyncio.run(run())
    else:
        with Arct(token="delete-mode", transport=httpx.MockTransport(handle)) as client:
            if scheduled is True:
                with pytest.raises(UncertainOperationError) as error:
                    getattr(client, resource).delete(ID, **kwargs)
                assert error.value.status == 204
            else:
                assert getattr(client, resource).delete(ID, **kwargs) is None
    assert len(calls) == 1
    assert calls[0].method == "DELETE"
    if scheduled is not None:
        assert calls[0].url.params["at_period_end"] == str(scheduled).lower()
