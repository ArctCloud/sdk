import asyncio
import json
from decimal import Decimal

import httpx
import pytest
from conftest import ACCOUNT
from pydantic import SecretStr, ValidationError as ModelValidationError


def sdk():
    from arct import Arct, AsyncArct
    return Arct, AsyncArct


def server(**fields):
    return dict(id="00000000-0000-0000-0000-000000000001", hostname="web-1", status="running", location="fra", plan="vm.small", plan_name=None, cpu_cores=1, ram_gb=1, storage_gb=10, bandwidth_tb=1, ipv4="192.0.2.1", ipv6=None, os="Ubuntu", login_user="root", labels=[], delete_protection=False, billing_period="monthly", price=1, next_due_date=None, cancel_at=None, created_at="2026-10-17T00:00:00Z", **fields)


def page(data, number=1, pages=1):
    return dict(data=data, pagination=dict(page=number, per_page=100, total=len(data), total_pages=pages))


def order():
    return dict(id="00000000-0000-0000-0000-000000000002", order_number="ORD-1", status="paid", payment_method="future", amount=1, currency="USD", created_at="2026-10-17T00:00:00Z", paid_at=None, server_id=None)


def created():
    return dict(order=order(), server=server(), password="one-time-secret")


def test_native_sync_in_running_loop_and_decimal():
    Arct, _ = sdk()
    async def run():
        transport = httpx.MockTransport(lambda r: httpx.Response(200, content=json.dumps(server()).replace('"price": 1,', '"price": 1.234567890123456789,').encode()))
        with Arct(token="private-token", transport=transport) as c:
            value = c.servers.get("00000000-0000-0000-0000-000000000001")
            assert value.price == Decimal("1.234567890123456789")
            assert "private-token" not in repr(c)
    asyncio.run(run())


def test_omitted_empty_nullable_and_secret_models():
    Arct, _ = sdk()
    bodies = []
    def handle(r):
        if r.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        bodies.append(json.loads(r.content))
        return httpx.Response(201, json=created())
    with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
        result = c.servers.create(hostname="web-1", location="fra", plan="vm.small", image_id="00000000-0000-0000-0000-000000000003")
        assert "ssh_key_ids" not in bodies[-1]
        assert "billing_period" not in bodies[-1]
        assert isinstance(result.password, SecretStr)
        assert result.password.get_secret_value() == "one-time-secret"
        assert "one-time-secret" not in repr(result)
        c.servers.create(hostname="web-1", location="fra", plan="vm.small", image_id="00000000-0000-0000-0000-000000000003", ssh_key_ids=[], coupon_code=None, enable_backups=False)
        assert bodies[-1]["ssh_key_ids"] == []
        assert bodies[-1]["coupon_code"] is None
        assert bodies[-1]["enable_backups"] is False
        with pytest.raises(ModelValidationError):
            c.servers.create(hostname="web-1", location="fra", plan="vm.small", image_id="00000000-0000-0000-0000-000000000003", ssh_key_ids=None)


def test_lazy_pagination_preserves_filters():
    Arct, _ = sdk()
    requests = []
    def handle(r):
        requests.append(r)
        n = int(r.url.params["page"])
        return httpx.Response(200, json=page([server()], n, 2))
    with Arct(token="token", transport=httpx.MockTransport(handle)) as c:
        values = c.servers.list(location="fra")
        assert not requests
        assert len(list(values)) == 2
        assert all(r.url.params["location"] == "fra" and r.url.params["per_page"] == "100" for r in requests)


async def test_async_native_methods_and_unknown_response_values():
    _, AsyncArct = sdk()
    async def handle(r):
        value = server()
        value.update(status="future_status", new_field="available")
        return httpx.Response(200, json=page([value]))
    async with AsyncArct(token="token", transport=httpx.MockTransport(handle)) as c:
        values = [x async for x in c.servers.list()]
        assert values[0].status == "future_status"
        assert values[0].new_field == "available"
