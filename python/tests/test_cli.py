import io
import json
import os
import stat
import subprocess
import sys

import httpx
import pytest
from conftest import ACCOUNT
from test_operations import CASES, SPEC, sample
from test_sdk import created, page, server

ID = "00000000-0000-0000-0000-000000000001"
CREATE = ["servers", "create", "--hostname", "web-1", "--location", "fra", "--plan", "vm.small", "--image", ID, "--yes"]
COMMANDS = [
    ["account", "get"],
    ["servers", "list", "--status", "running", "--location", "fra", "--page", "2", "--per-page", "50"],
    CREATE + ["--billing-period", "yearly", "--ssh-key", "", "--coupon-code", "CODE", "--enable-backups=false"],
    ["servers", "get", ID],
    ["servers", "delete", ID, "--yes"],
    ["servers", "update", ID, "--hostname", "new-host", "--delete-protection=false", "--label", ""],
    ["locations", "list", "--page", "2", "--per-page", "50"],
    ["plans", "list", "--location", "fra", "--page", "2", "--per-page", "50"],
    ["images", "list", "--location", "fra", "--page", "2", "--per-page", "50"],
    ["invoices", "list", "--page", "2", "--per-page", "50"],
    ["invoices", "get", ID],
    ["ssh-keys", "list", "--page", "2", "--per-page", "50"],
    ["ssh-keys", "create", "--name", "laptop", "--public-key", "ssh-ed25519 example"],
    ["ssh-keys", "get", ID],
    ["ssh-keys", "delete", ID, "--yes"],
    ["servers", "start", ID],
    ["servers", "stop", ID],
    ["servers", "restart", ID],
    ["servers", "reinstall", ID, "--image", ID, "--ssh-key", "", "--hostname", "fresh", "--yes"],
    ["servers", "cancel-deletion", ID, "--yes"],
    ["servers", "resize-options", ID],
    ["servers", "resize", ID, "--plan", "vm.medium", "--expected-amount", "4.12", "--yes"],
    ["servers", "delete", ID, "--at-period-end", "--yes"],
    ["servers", "resize", ID, "--plan", "vm.medium", "--expected-amount", "4.12", "--yes"],
]


@pytest.fixture
def cli(monkeypatch, tmp_path):
    from arct import Arct, _cli
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("ARCT_TOKEN", "secret-token")
    monkeypatch.delenv("ARCT_BASE_URL", raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    seen = []

    def setup(handler):
        def factory(**kwargs):
            return Arct(**kwargs, transport=httpx.MockTransport(handler))
        monkeypatch.setattr(_cli, "Arct", factory)
        return _cli.main
    return setup, seen, tmp_path / "arct" / "config.json"


@pytest.mark.parametrize("args,case", list(zip(COMMANDS, CASES)), ids=["-".join(a[:2]) for a in COMMANDS])
def test_wire_commands(cli, capsys, args, case):
    setup, seen, _ = cli
    resource, action, _, _, method, path, query, body, status = case

    def handle(request):
        if request.url.path == "/v1/account" and path != "/account":
            return httpx.Response(200, json=ACCOUNT)
        seen.append(request)
        assert request.method == method
        assert request.url.path == "/v1" + path
        assert dict(request.url.params) == query
        assert (json.loads(request.content) if request.content else None) == body
        schema_path = next(p for p in SPEC["paths"] if p.replace("{server_id}", ID).replace("{invoice_id}", ID).replace("{key_id}", ID) == path)
        response = SPEC["paths"][schema_path][method.lower()]["responses"][str(status)]
        schema = response.get("content", {}).get("application/json", {}).get("schema")
        return httpx.Response(status, json=sample(schema)) if schema else httpx.Response(status)

    assert setup(handle)(["--output", "json"] + args) == 0
    out, err = capsys.readouterr()
    assert len(seen) == 1
    json.loads(out)
    assert "secret-token" not in out + err


@pytest.mark.parametrize("args", [
    CREATE[:-1], ["servers", "delete", ID], ["servers", "reinstall", ID, "--image", ID],
    ["servers", "delete", ID, "--at-period-end", "--wait", "--yes"],
    ["servers", "resize", ID, "--plan", "vm.medium", "--expected-amount", "NaN", "--yes"],
    ["servers", "resize", ID, "--plan", "vm.medium", "--expected-amount", "-1", "--yes"],
    ["servers", "get"], ["servers", "get", "invalid"], ["servers", "get", ID, "--wat"],
    ["servers", "list", "--status", "error"], ["servers", "list", "--per-page", "101"],
    ["servers", "get", ID, "--wait"], ["servers", "start", ID, "--timeout", "inf"],
    ["account", "get", "--columns", "id", "--output", "json"],
    CREATE + ["--coupon-code", "CODE", "--coupon-code-null"],
    ["ssh-keys", "create", "--name", "key", "--public-key", "PRIVATE KEY"],
])
def test_usage_prevents_requests(cli, capsys, args):
    setup, seen, _ = cli
    def handle(request):
        seen.append(request)
        return httpx.Response(200, json={})
    assert setup(handle)(args + ["--output=json"]) == 2
    assert seen == []
    assert "error" in capsys.readouterr().err


@pytest.mark.parametrize("extra,expected", [
    ([], {"hostname": "web-1", "location": "fra", "plan": "vm.small", "image_id": ID}),
    (["--coupon-code-null", "--ssh-key", "", "--enable-backups=false"], {"hostname": "web-1", "location": "fra", "plan": "vm.small", "image_id": ID, "coupon_code": None, "ssh_key_ids": [], "enable_backups": False}),
])
def test_create_omissions(cli, capsys, extra, expected):
    setup, seen, _ = cli
    def handle(request):
        if request.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        seen.append(json.loads(request.content))
        return httpx.Response(201, json=created())
    assert setup(handle)(CREATE + extra) == 0
    assert seen == [expected]


def test_pagination_and_columns(cli, capsys):
    setup, seen, _ = cli
    def handle(request):
        seen.append(dict(request.url.params))
        n = int(request.url.params["page"])
        return httpx.Response(200, json=page([server()], n, 2))
    assert setup(handle)(["servers", "--columns", "hostname,status", "list", "--all", "--location", "fra", "--no-header"]) == 0
    assert capsys.readouterr().out.split() == ["web-1", "running", "web-1", "running"]
    assert seen == [{"page": "1", "per_page": "20", "location": "fra"}, {"page": "2", "per_page": "20", "location": "fra"}]


@pytest.mark.parametrize("action", ["create", "reinstall", "stop", "start", "restart", "wait", "delete"])
def test_wait_retains_response_and_final_server(cli, capsys, action):
    setup, seen, _ = cli
    def handle(request):
        if request.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        seen.append(request.method)
        if request.method == "DELETE":
            return httpx.Response(204)
        if request.method == "POST":
            if action == "create":
                return httpx.Response(201, json=created())
            if action == "reinstall":
                initial = server()
                initial["status"] = "reinstalling"
                return httpx.Response(202, json={"server": initial, "password": "one-time-secret", "access_token": "hidden"})
            value = server()
            value["status"] = "restarting" if action == "restart" else "running"
            return httpx.Response(202, json=value)
        if action == "delete":
            return httpx.Response(404, json={"error": {"code": "not_found"}})
        value = server()
        value["status"] = "stopped" if action == "stop" else "running"
        return httpx.Response(200, json=value)
    args = CREATE if action == "create" else ["servers", action, ID, "--yes"]
    if action != "wait":
        args = args + ["--wait"]
    if action in ("create", "reinstall"):
        args = args + ["--show-password"]
    if action == "reinstall":
        args += ["--image", ID]
    assert setup(handle)(args + ["--output=json"]) == 0
    out = json.loads(capsys.readouterr().out)
    if action == "delete":
        assert out == {"id": ID, "deleted": True}
    elif action == "wait":
        assert out["status"] == "running"
    else:
        assert out["final_server"]["status"] == ("stopped" if action == "stop" else "running")
        if action in ("create", "reinstall"):
            assert out["password"] == "one-time-secret"
            assert "hidden" not in json.dumps(out)
        else:
            assert out["status"] == ("restarting" if action == "restart" else "running")
    assert seen.count("POST") <= 1


@pytest.mark.parametrize("interrupt,code", [(False, 3), (True, 130)])
def test_wait_failure_keeps_password_and_order(cli, capsys, interrupt, code):
    setup, seen, _ = cli
    def handle(request):
        if request.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        seen.append(request.method)
        if request.method == "POST":
            return httpx.Response(201, json=created())
        if interrupt:
            raise KeyboardInterrupt
        value = server()
        value["status"] = "provisioning"
        return httpx.Response(200, json=value)
    assert setup(handle)(CREATE + ["--wait", "--timeout", "10ms", "--show-password", "--output=json"]) == code
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert out["password"] == "one-time-secret"
    assert out["order"]["order_number"] == "ORD-1"
    assert "wait_error" in out
    assert seen.count("POST") == 1
    assert "secret-token" not in captured.out + captured.err


def test_resize_quote_precedes_confirmation_and_preserves_decimal(cli, capsys):
    setup, seen, _ = cli
    def handle(request):
        if request.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        seen.append(request)
        if request.method == "GET":
            schema = SPEC["components"]["schemas"]["ResizeOptions"]
            options = sample(schema)
            plan = sample(SPEC["components"]["schemas"]["ResizePlan"])
            plan.update(slug="vm.medium", eligible=True, amount_due_today="4.120000000000000001")
            options.update(can_resize=True, plans=[plan])
            return httpx.Response(200, json=options)
        response = sample(SPEC["components"]["schemas"]["ResizeResponse"])
        return httpx.Response(202, json=response)
    main = setup(handle)
    args = ["servers", "resize", ID, "--plan", "vm.medium", "--output=json"]
    assert main(args) == 2
    assert [r.method for r in seen] == ["GET"]
    assert "4.120000000000000001" in capsys.readouterr().err
    seen.clear()
    assert main(args + ["--yes"]) == 0
    assert [r.method for r in seen] == ["GET", "POST"]
    assert json.loads(seen[-1].content)["expected_amount"] == "4.120000000000000001"


def test_auth_stdin_contexts_and_private_config(cli, monkeypatch, capsys):
    setup, _, config = cli
    monkeypatch.delenv("ARCT_TOKEN")
    monkeypatch.setattr(sys, "stdin", io.StringIO("saved-token\n"))
    main = setup(lambda request: httpx.Response(200, json=ACCOUNT))
    assert main(["auth", "login", "--context", "work", "--base-url", "https://example.com", "--output=json"]) == 0
    captured = capsys.readouterr()
    assert "saved-token" not in captured.out + captured.err
    assert json.loads(config.read_text()) == {"active": "work", "contexts": {"work": {"token": "saved-token", "base_url": "https://example.com"}}}
    if os.name != "nt":
        assert stat.S_IMODE(config.stat().st_mode) == 0o600
        assert stat.S_IMODE(config.parent.stat().st_mode) == 0o700
    assert main(["context", "list", "--output=json"]) == 0
    assert json.loads(capsys.readouterr().out) == [{"name": "work", "active": True, "base_url": "https://example.com"}]
    assert main(["context", "use", "work"]) == 0
    assert main(["auth", "status"]) == 0
    assert main(["auth", "logout", "--context", "work"]) == 0
    assert json.loads(config.read_text()) == {"active": "", "contexts": {}}


@pytest.mark.parametrize("unsafe", ["symlink", "directory", "permissions", "invalid"])
def test_unsafe_config_is_rejected(cli, capsys, unsafe):
    setup, seen, config = cli
    config.parent.mkdir()
    if unsafe == "symlink":
        other = config.parent / "other"
        other.write_text("{}")
        config.symlink_to(other)
    elif unsafe == "directory":
        config.mkdir()
    else:
        config.write_text("not json" if unsafe == "invalid" else "{}")
        config.chmod(0o644 if unsafe == "permissions" else 0o600)
    if unsafe == "permissions" and os.name == "nt":
        pytest.skip("POSIX permissions")
    def handle(request):
        seen.append(request)
        return httpx.Response(200, json=ACCOUNT)
    assert setup(handle)(["account", "get", "--output=json"]) == 1
    assert seen == []
    assert "error" in capsys.readouterr().err


def test_public_key_stdin_and_secret_rendering(cli, monkeypatch, capsys):
    setup, seen, _ = cli
    monkeypatch.setattr(sys, "stdin", io.StringIO("ssh-ed25519 AAAA\n"))
    def handle(request):
        if request.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        seen.append(json.loads(request.content))
        return httpx.Response(201, json={"id": ID, "name": "key", "fingerprint": "fingerprint", "created_at": "2026-10-17T00:00:00Z"})
    assert setup(handle)(["ssh-keys", "create", "--name", "key", "--public-key-file", "-"]) == 0
    assert seen == [{"name": "key", "public_key": "ssh-ed25519 AAAA"}]


@pytest.mark.parametrize("status,body,code", [
    (401, {"error": {"code": "invalid_token", "message": "secret-token"}}, 1),
    (409, {"error": {"code": "payment_pending", "details": {"order_intent_id": "support"}}}, 3),
])
def test_json_errors_and_exit_codes(cli, capsys, status, body, code):
    setup, _, _ = cli
    assert setup(lambda request: httpx.Response(status, json=body))(["account", "get", "--output=json"]) == code
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == body["error"]["code"]
    assert "secret-token" not in captured.err


def test_help_version_and_module_invocation(cli, capsys):
    setup, _, _ = cli
    main = setup(lambda request: pytest.fail("Help must be local"))
    assert main(["servers", "create", "--help"]) == 0
    help_output = capsys.readouterr().out
    assert "--ssh-key" in help_output
    assert "--yes [BOOL]" in help_output
    assert "--no-header [BOOL]" in help_output
    assert main(["--version"]) == 0
    from arct import __version__
    assert capsys.readouterr().out.strip() == __version__
    result = subprocess.run([sys.executable, "-m", "arct", "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.strip() == __version__


@pytest.mark.parametrize("args", [
    ["servers", "get", ID.replace("-", "")],
    CREATE + ["--image", ID.replace("-", "")],
    CREATE + ["--ssh-key", ID.replace("-", "")],
    ["servers", "update", ID],
    ["servers", "update", ID, "--label", "bad label"],
    ["servers", "update", ID, "--label", "ok", "--label", ""],
])
def test_legacy_validation_prevents_invalid_requests(cli, args):
    setup, seen, _ = cli
    def handle(request):
        seen.append(request)
        return httpx.Response(200, json=ACCOUNT if request.url.path.endswith("/account") else server())
    assert setup(handle)(args) == 2
    assert seen == []


@pytest.mark.parametrize("show", [False, True])
def test_wait_table_preserves_order_and_controls_passwords(cli, capsys, show):
    setup, _, _ = cli
    def handle(request):
        if request.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        value = created() if request.method == "POST" else server()
        value.update(access_token="hidden-token", nested={"db_password": "hidden-password", "note": "secret-token"})
        return httpx.Response(200, json=value)
    assert setup(handle)(CREATE + ["--wait"] + (["--show-password"] if show else [])) == 0
    out = capsys.readouterr().out
    assert "ORD-1" in out and "running" in out and "final_server" not in out
    assert ("one-time-secret" in out) == show
    assert all(secret not in out for secret in ("hidden-token", "hidden-password", "secret-token"))


def test_json_api_error_retains_kind(cli, capsys):
    setup, _, _ = cli
    main = setup(lambda request: httpx.Response(401, json={"error": {"code": "invalid_token", "message": "invalid"}}))
    assert main(["account", "get", "--output=json"]) == 1
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["kind"] == "AuthenticationError"
    assert error["status"] == 401


@pytest.mark.parametrize("platform,folder", [
    ("linux", ".config"), ("darwin", "Library/Application Support"), ("win32", "AppData/Roaming"),
])
def test_platform_config_locations(monkeypatch, tmp_path, platform, folder):
    from arct import _cli_config
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    monkeypatch.setattr(sys, "platform", platform)
    assert _cli_config.config_file() == tmp_path / folder / "arct" / "config.json"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "custom"))
    assert _cli_config.config_file() == tmp_path / "custom" / "arct" / "config.json"


def test_saved_context_and_environment_precedence(cli, monkeypatch):
    setup, seen, config = cli
    config.parent.mkdir()
    config.write_text(json.dumps({"active": "work", "contexts": {"work": {"token": "saved-token", "base_url": "https://saved.example/v1"}}}))
    config.chmod(0o600)
    def handle(request):
        seen.append((request.url.host, request.headers["authorization"]))
        return httpx.Response(200, json=ACCOUNT)
    main = setup(handle)
    monkeypatch.delenv("ARCT_TOKEN")
    assert main(["account", "get"]) == 0
    monkeypatch.setenv("ARCT_TOKEN", "env-token")
    monkeypatch.setenv("ARCT_BASE_URL", "https://env.example/v1")
    assert main(["account", "get"]) == 0
    assert main(["--base-url", "https://flag.example/v1", "account", "get"]) == 0
    assert seen == [("saved.example", "Bearer saved-token"), ("env.example", "Bearer env-token"), ("flag.example", "Bearer env-token")]


@pytest.mark.parametrize("action", ["delete", "resize"])
def test_wait_timeout_is_bounded_without_mutation_replay(cli, capsys, action):
    setup, seen, _ = cli
    def handle(request):
        if request.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        seen.append(request.method)
        if request.method == "DELETE":
            return httpx.Response(204)
        if request.method == "POST":
            value = sample(SPEC["components"]["schemas"]["ResizeResponse"])
            value.update(status="pending_payment", to_plan="vm.medium")
            return httpx.Response(202, json=value)
        if request.url.path.endswith("resize-options"):
            return httpx.Response(200, json=sample(SPEC["components"]["schemas"]["ResizeOptions"]))
        return httpx.Response(200, json=server())
    args = ["servers", action, ID, "--yes", "--wait", "--timeout", "10ms", "--output=json"]
    if action == "resize":
        args += ["--plan", "vm.medium", "--expected-amount", "4.12"]
    assert setup(handle)(args) == 3
    captured = capsys.readouterr()
    assert "wait_error" in json.loads(captured.out)
    assert seen.count("POST" if action == "resize" else "DELETE") == 1
    assert "secret-token" not in captured.out + captured.err


def test_resize_wait_preserves_acknowledgement(cli, capsys):
    setup, seen, _ = cli
    def handle(request):
        if request.url.path.endswith("/account"):
            return httpx.Response(200, json=ACCOUNT)
        seen.append(request.method)
        if request.method == "GET":
            assert request.extensions["timeout"]["read"] <= 1
        if request.method == "POST":
            value = sample(SPEC["components"]["schemas"]["ResizeResponse"])
            value.update(to_plan="vm.medium", status="applied")
        elif request.url.path.endswith("resize-options"):
            value = sample(SPEC["components"]["schemas"]["ResizeOptions"])
            value.update(current_plan="vm.medium", pending_resize=None)
        else:
            value = server()
            value["plan"] = "vm.medium"
        return httpx.Response(200, json=value)
    args = ["servers", "resize", ID, "--plan", "vm.medium", "--expected-amount", "4.12", "--yes", "--wait", "--timeout", "1s", "--output=json"]
    assert setup(handle)(args) == 0
    value = json.loads(capsys.readouterr().out)
    assert value["status"] == "applied"
    assert value["final_server"]["plan"] == "vm.medium"
    assert value["final_resize_options"]["current_plan"] == "vm.medium"
    assert value["final_resize_options"]["pending_resize"] is None
    assert seen == ["POST", "GET", "GET", "GET"]


def test_config_atomic_failure_preserves_previous_credentials(cli, monkeypatch):
    from arct import _cli_config
    _, _, path = cli
    original = {"active": "old", "contexts": {"old": {"token": "old-token"}}}
    _cli_config.save(original)
    def fail_replace(*args):
        raise OSError("disk failure")
    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError):
        _cli_config.save({"active": "new", "contexts": {"new": {"token": "new-token"}}})
    assert _cli_config.load() == original
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize("contexts", [False, 0, [], ""])
def test_invalid_context_mapping_is_rejected(cli, capsys, contexts):
    setup, _, path = cli
    path.parent.mkdir()
    path.write_text(json.dumps({"active": "", "contexts": contexts}))
    path.chmod(0o600)
    assert setup(lambda request: pytest.fail("Invalid config must remain local"))(["auth", "status", "--output=json"]) == 1
    assert "invalid credential configuration" in capsys.readouterr().err


def test_rejected_token_flag_does_not_echo_value(cli, capsys):
    setup, _, _ = cli
    main = setup(lambda request: pytest.fail("Token flags must remain local"))
    assert main(["account", "get", "--token", "untracked-secret", "--output=json"]) == 2
    captured = capsys.readouterr()
    assert "untracked-secret" not in captured.out + captured.err
