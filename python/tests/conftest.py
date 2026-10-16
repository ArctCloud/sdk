import json
from pathlib import Path
import pytest

FIXTURES = json.loads((Path(__file__).resolve().parents[2] / "api/test-cases.json").read_text())
ACCOUNT = dict(id="10000000-0000-0000-0000-000000000001", email="user@example.com", name=None, email_verified=True, created_at="2026-10-17T00:00:00Z", token=dict(id="20000000-0000-0000-0000-000000000001", name="test", scope="read_write", expires_at=None))


@pytest.fixture(autouse=True)
def reset_limits():
    from arct import _limits
    _limits._EVENTS.clear()
    _limits._ACCOUNTS.clear()
