import argparse
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import getpass
import json
import math
import os
from pathlib import Path
import re
import signal
import sys
from uuid import UUID

from pydantic import BaseModel, SecretStr, ValidationError as ModelValidationError

from . import Arct, __version__
from . import _cli_config as config
from ._resources import deadline_scope, quote_amount
from ._transport import remaining
from .errors import APIError, ChargeUnknownError, NotFoundError, UncertainOperationError, safe
from .models import CreateServerRequest, ResizeServerRequest, ServerReinstall, ServerUpdate, SshKeyCreate

COMMANDS = {
    "account": "get", "servers": "list get create update delete start stop restart reinstall resize-options resize cancel-deletion wait",
    "locations": "list", "plans": "list", "images": "list", "ssh-keys": "list get create delete",
    "invoices": "list get", "auth": "login logout status", "context": "list use delete",
}
BOOLS = {"no-header", "yes", "all", "wait", "show-password", "coupon-code-null", "enable-backups", "delete-protection", "at-period-end"}
VALUES = {"context", "base-url", "output", "columns", "page", "per-page", "timeout", "status", "hostname", "image", "ssh-key", "plan", "billing-period", "coupon-code", "label", "expected-amount", "location", "name", "public-key", "public-key-file"}
STATUSES = "provisioning running stopped restarting reinstalling restoring deleting suspended pre_order".split()


class UsageError(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError("unrecognized arguments; run arct --help" if message.startswith("unrecognized arguments:") else message)


def _bool(value):
    if value in ("1", "t", "T", "TRUE", "true", "True"):
        return True
    if value in ("0", "f", "F", "FALSE", "false", "False"):
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def _parser(args):
    positions, normalized = [], []
    skip = False
    for index, arg in enumerate(args):
        if skip:
            normalized.append(arg)
            skip = False
            continue
        name = arg.lstrip("-").split("=", 1)[0]
        if arg == "--":
            positions.extend(args[index + 1:])
            normalized.extend(args[index:])
            break
        if arg.startswith("-") and arg != "-":
            normalized.append(arg + "=true" if name in BOOLS and "=" not in arg else arg)
            skip = name in VALUES and "=" not in arg
        else:
            positions.append(arg)
            normalized.append(arg)
    resource, action = (positions + ["", ""])[:2]
    parser = Parser(prog="arct", add_help=False, allow_abbrev=False, argument_default=argparse.SUPPRESS,
                    description="Usage: arct <resource> <action> [ID] [flags]")

    def add(name, **kwargs):
        if kwargs.get("type") is _bool:
            kwargs.update(nargs="?", const=True, metavar="BOOL")
        parser.add_argument("--" + name, "-" + name, **kwargs)
    for name in ("context", "base-url", "columns"):
        add(name)
    add("output", default="table", choices=("table", "json"))
    for name in ("no-header", "yes"):
        add(name, type=_bool)
    if action == "list" and resource != "context":
        add("all", type=_bool)
        add("page", type=int)
        add("per-page", type=int)
    if resource == "servers":
        if action in "create start stop restart reinstall resize delete".split():
            add("wait", type=_bool)
        if action in "create start stop restart reinstall resize delete wait".split():
            add("timeout", default="600s")
        if action in ("list", "wait"):
            add("status", **({"default": "running"} if action == "wait" else {}))
        if action in ("create", "update", "reinstall"):
            add("hostname")
        if action in ("create", "reinstall"):
            add("image")
            add("ssh-key", action="append")
            add("show-password", type=_bool)
        if action in ("create", "resize"):
            add("plan")
        if action == "create":
            add("billing-period")
            add("coupon-code")
            add("coupon-code-null", type=_bool)
            add("enable-backups", type=_bool)
        if action == "update":
            add("delete-protection", type=_bool)
            add("label", action="append")
        if action == "delete":
            add("at-period-end", type=_bool)
        if action == "resize":
            add("expected-amount")
    if resource == "servers" and action in ("create", "list") or resource in ("plans", "images") and action == "list":
        add("location")
    if resource == "ssh-keys" and action == "create":
        for name in ("name", "public-key", "public-key-file"):
            add(name)
    parser.add_argument("positions", nargs="*")
    return parser, normalized


def _uuid(value):
    identifier = UUID(value)
    if str(identifier) != value.lower():
        raise UsageError("identifier must be a UUID")
    return identifier


def _duration(value):
    try:
        seconds = float(value)
    except ValueError:
        parts = re.findall(r"(\d+(?:\.\d*)?|\.\d+)(ns|us|µs|μs|ms|s|m|h)", value)
        if not parts or "".join(n + unit for n, unit in parts) != value:
            raise UsageError("invalid --timeout") from None
        seconds = sum(float(n) * {"ns": 1e-9, "us": 1e-6, "µs": 1e-6, "μs": 1e-6, "ms": 1e-3, "s": 1, "m": 60, "h": 3600}[unit] for n, unit in parts)
    if not math.isfinite(seconds) or not 0 < seconds <= (2**63 - 1) / 1e9:
        raise UsageError("--timeout must be positive and finite")
    return seconds


def _json(value):
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("invalid decimal response")
        return str(value)
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(k) + ":" + _json(v) for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(map(_json, value)) + "]"
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


class App:
    def __init__(self):
        self.tokens = {os.environ.get("ARCT_TOKEN", "")} - {""}

    def clean(self, value, reveal=False):
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="python", exclude_unset=True)
        if isinstance(value, SecretStr):
            value = value.get_secret_value() if reveal else "[REDACTED]"
        if isinstance(value, dict):
            out = {}
            for key, item in value.items():
                sensitive = any(word in key.lower() for word in ("password", "authorization", "token", "secret")) and key != "token_id"
                if sensitive and item is not None and not (key == "token" and isinstance(item, (dict, BaseModel))) and not (reveal and key == "password"):
                    out[key] = "[REDACTED]"
                else:
                    out[key] = self.clean(item, reveal)
            return out
        if isinstance(value, (list, tuple)):
            return [self.clean(item, reveal) for item in value]
        if isinstance(value, (UUID, date, datetime)):
            value = value.isoformat() if isinstance(value, (date, datetime)) else str(value)
        if isinstance(value, str):
            for token in self.tokens:
                value = value.replace(token, "[REDACTED]")
            return safe(value)
        return value

    def message(self, text):
        print(self.clean(text), file=sys.stderr)

    def load(self):
        value = config.load()
        self.tokens.update(item.get("token", "") for item in value["contexts"].values() if item.get("token"))
        return value

    def client(self, f):
        cfg = self.load()
        name = f.get("context") or cfg["active"]
        stored = cfg["contexts"].get(name, {})
        token = os.environ.get("ARCT_TOKEN") or stored.get("token")
        if f.get("context") and name not in cfg["contexts"] and not os.environ.get("ARCT_TOKEN"):
            raise UsageError("unknown context " + name)
        if not token:
            raise UsageError("authentication required: set ARCT_TOKEN or run arct auth login")
        self.tokens.add(token)
        base = f.get("base_url") or os.environ.get("ARCT_BASE_URL") or stored.get("base_url")
        return Arct(token=token, **({"base_url": base} if base else {}))

    def confirm(self, f, text):
        self.message(text)
        if f.get("yes"):
            return
        if not sys.stdin.isatty():
            raise UsageError("confirmation required: pass --yes for noninteractive use")
        print("Continue? [y/N] ", end="", file=sys.stderr, flush=True)
        if sys.stdin.readline().strip().lower() != "y":
            raise UsageError("operation not confirmed")

    def local(self, resource, action, ids, f):
        cfg = self.load()
        name = f.get("context") or cfg["active"] or "default"
        contexts = cfg["contexts"]
        if resource == "context":
            if action == "list":
                if ids:
                    raise UsageError("context list takes no identifier")
                return [{"name": name, "active": cfg["active"] == name, "base_url": contexts[name].get("base_url", "")} for name in sorted(contexts)]
            if len(ids) != 1:
                raise UsageError("context name required")
            name = ids[0]
            if name not in contexts:
                raise UsageError("unknown context " + name)
            if action == "use":
                cfg["active"] = name
            else:
                del contexts[name]
                if cfg["active"] == name:
                    cfg["active"] = ""
            config.save(cfg)
            return {"context": name, "action": action}
        if ids:
            raise UsageError("auth command takes no identifier")
        if action == "status":
            source = "ARCT_TOKEN" if os.environ.get("ARCT_TOKEN") else "context" if contexts.get(name, {}).get("token") else "none"
            return {"credential_source": source, "context": name, "configured": source != "none"}
        if action == "logout":
            contexts.pop(name, None)
            if cfg["active"] == name:
                cfg["active"] = ""
            config.save(cfg)
            return {"context": name, "logged_out": True}
        if len(name) > 100 or any(char in name for char in "\r\n\t/"):
            raise UsageError("invalid context name")
        token = os.environ.get("ARCT_TOKEN")
        if not token:
            if sys.stdin.isatty():
                token = getpass.getpass("Dashboard API token: ", stream=sys.stderr)
            else:
                print("Dashboard API token: ", end="", file=sys.stderr, flush=True)
                token = sys.stdin.readline(16385).strip()
        if not token or len(token) > 16384:
            raise UsageError("token required")
        self.tokens.add(token)
        base = f.get("base_url") or os.environ.get("ARCT_BASE_URL") or ""
        with Arct(token=token, **({"base_url": base} if base else {})) as client:
            account = client.account.get()
        contexts[name] = {"token": token, **({"base_url": base} if base else {})}
        cfg["active"] = name
        config.save(cfg)
        return {"context": name, "account_id": account.id, "validated": True}

    def remote(self, resource, action, ids, f):
        needs_id = action in "get update delete start stop restart reinstall resize-options resize cancel-deletion wait".split() and resource != "account"
        if len(ids) != int(needs_id):
            raise UsageError("unexpected or missing identifier")
        identifier = _uuid(ids[0]) if needs_id else None
        timeout = _duration(f.get("timeout", "600s"))
        kwargs = {}
        if action == "list":
            if not 1 <= f.get("page", 1) <= 100000 or not 1 <= f.get("per_page", 20) <= 100:
                raise UsageError("invalid page or per-page")
            kwargs = {key: f[key] for key in ("page", "per_page", "location", "status") if key in f}
            if "status" in f and f["status"] not in STATUSES:
                raise UsageError("unsupported status filter")
        if resource == "servers":
            fields = {
                "create": ("hostname", "location", "plan", "image", "billing_period", "ssh_key", "coupon_code", "enable_backups"),
                "update": ("hostname", "delete_protection", "label"),
                "reinstall": ("image", "ssh_key", "hostname"), "resize": ("plan",), "delete": ("at_period_end",),
            }.get(action, ())
            names = {"image": "image_id", "ssh_key": "ssh_key_ids", "label": "labels"}
            kwargs = kwargs | {names.get(key, key): ([] if f[key] == [""] else f[key]) for key in fields if key in f}
            if "image_id" in kwargs:
                _uuid(kwargs["image_id"])
            for key in kwargs.get("ssh_key_ids", []):
                _uuid(key)
            if action == "update":
                if not kwargs:
                    raise UsageError("at least one update field required")
                if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,62}", label) for label in kwargs.get("labels", [])):
                    raise UsageError("invalid label")
            if action == "create" and f.get("coupon_code_null"):
                if "coupon_code" in f:
                    raise UsageError("coupon flags conflict")
                kwargs["coupon_code"] = None
            if action == "resize" and "expected_amount" in f:
                raw = f["expected_amount"]
                if not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", raw):
                    raise UsageError("expected amount must be a nonnegative decimal")
                try:
                    amount = Decimal(raw)
                except InvalidOperation:
                    raise UsageError("expected amount must be a nonnegative decimal") from None
                if not amount.is_finite():
                    raise UsageError("expected amount must be a nonnegative decimal")
                kwargs["expected_amount"] = amount
            if action == "wait" and f["status"] not in STATUSES + ["error"]:
                raise UsageError("invalid target status")
            if action == "delete" and f.get("at_period_end") and f.get("wait"):
                raise UsageError("scheduled deletion does not support --wait")
            model = {"create": CreateServerRequest, "update": ServerUpdate, "reinstall": ServerReinstall, "resize": ResizeServerRequest}.get(action)
            if model:
                model.model_validate(kwargs)
        if resource == "ssh-keys" and action == "create":
            if "public_key" in f and "public_key_file" in f:
                raise UsageError("public key flags conflict")
            key = f.get("public_key", "")
            if f.get("public_key_file"):
                try:
                    if f["public_key_file"] == "-":
                        key = sys.stdin.read(8194).strip()
                    else:
                        with Path(f["public_key_file"]).open(encoding="utf-8") as stream:
                            key = stream.read(8194).strip()
                except (OSError, UnicodeError):
                    raise UsageError("cannot read public key file") from None
            if "PRIVATE KEY" in key:
                raise UsageError("a public key is required")
            kwargs = {"name": f.get("name", ""), "public_key": key}
            SshKeyCreate.model_validate(kwargs)
        if resource == "servers" and action == "create":
            self.confirm(f, f"Create {kwargs['hostname']}: plan={kwargs['plan']} location={kwargs['location']} billing={f.get('billing_period', 'monthly')}. A saved card is charged; final charges depend on promotions, backups and billing period.")
        if action == "delete" or resource == "servers" and action in ("reinstall", "cancel-deletion"):
            self.confirm(f, f"Confirm {resource} {action} {identifier}; this may destroy data or change billing.")
        with self.client(f) as client:
            api = getattr(client, resource.replace("-", "_"))
            if action == "wait":
                return api.wait_until(identifier, f["status"], timeout=timeout)
            if resource == "servers" and action == "resize":
                if "expected_amount" not in kwargs:
                    kwargs["expected_amount"] = quote_amount(api.resize_options(identifier), kwargs["plan"])
                self.confirm(f, f"Resize {identifier} to {kwargs['plan']}: quoted charge USD {kwargs['expected_amount']}. This exact amount will be submitted; changed prices require a new decision.")
            if action == "list":
                if f.get("all"):
                    return list(api.list(**({"page": 1, "per_page": 20} | kwargs)))
                return api.list_page(**kwargs)
            method = getattr(api, action.replace("-", "_"))
            result = method(*([identifier] if needs_id else []), **kwargs)
            if f.get("wait"):
                try:
                    self.message("Waiting for completion; interruption stops polling only.")
                    if action == "delete":
                        with deadline_scope(timeout) as deadline:
                            while True:
                                remaining(deadline)
                                try:
                                    api.get(identifier)
                                except NotFoundError:
                                    return {"id": identifier, "deleted": True}
                                client._transport.sleep(5, deadline)
                    if action == "resize":
                        with deadline_scope(timeout):
                            final = api.wait_resize(identifier, result, timeout=timeout)
                            options = api.resize_options(identifier)
                    else:
                        final = api.wait_until(result, "stopped" if action == "stop" else "running", timeout=timeout)
                    out = self.clean(result, True) | {"final_server": final}
                    if action == "resize":
                        out["final_resize_options"] = options
                    return out
                except (Exception, KeyboardInterrupt) as error:
                    kept = self.clean(result, True) if result is not None else {"id": identifier}
                    self.render(kept | {"wait_error": str(error) or "interrupted"}, f)
                    raise
            if resource == "servers" and action in ("start", "stop", "restart", "reinstall"):
                self.message("Operation accepted; completion is asynchronous.")
            if resource == "servers" and action == "resize" and result.status == "pending_payment":
                self.message("Resize is pending payment; the plan has not been applied.")
            return result

    def render(self, value, f):
        value = self.clean(value, f.get("show_password", False))
        if f["output"] == "json":
            print(_json(value))
            return
        if value is None:
            print("Done")
            return
        if isinstance(value, dict):
            if isinstance(value.get("final_server"), dict):
                final = value.pop("final_server")
                value.pop("server", None)
                value.update(final)
            if isinstance(value.get("data"), list):
                value = value["data"]
            else:
                self.table([[key, self.display(value[key])] for key in sorted(value)])
                return
        if isinstance(value, list):
            columns = [column for column in f.get("columns", "").split(",") if column]
            if not columns:
                columns = [key for key in "id code slug name hostname status location plan invoice_number total active base_url".split() if any(isinstance(row, dict) and key in row for row in value)]
            rows = [] if f.get("no_header") or not columns else [columns]
            rows += [[self.display(row.get(key)) for key in columns] for row in value]
            self.table(rows)
        else:
            print(self.display(value))

    @staticmethod
    def display(value):
        if value is None:
            return "-"
        return value.replace("\n", " ").replace("\r", " ").replace("\t", " ") if isinstance(value, str) else _json(value)

    @staticmethod
    def table(rows):
        widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))] if rows else []
        for row in rows:
            print("  ".join(item.ljust(width) for item, width in zip(row, widths)).rstrip())

    def failure(self, error, json_mode):
        code = 130 if isinstance(error, KeyboardInterrupt) else 3 if isinstance(error, (TimeoutError, UncertainOperationError, ChargeUnknownError)) else 2 if isinstance(error, (UsageError, ValueError, ModelValidationError)) else 1
        message = str(error) or "interrupted"
        if isinstance(error, ModelValidationError):
            message = "; ".join(".".join(map(str, item["loc"])) + ": " + item["msg"] for item in error.errors(include_input=False))
        if json_mode:
            value = {"code": error.code, "message": message, "status": error.status, "details": error.details, "kind": type(error).__name__} if isinstance(error, APIError) else {"code": "error", "message": message}
            print(_json({"error": self.clean(value)}), file=sys.stderr)
        else:
            self.message(message)
        return code


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    app = App()
    json_mode = any(arg in ("--output=json", "-output=json") or arg in ("--output", "-output") and index + 1 < len(args) and args[index + 1] == "json" for index, arg in enumerate(args))
    previous = None
    if hasattr(signal, "SIGTERM"):
        try:
            previous = signal.signal(signal.SIGTERM, signal.default_int_handler)
        except ValueError:
            pass
    try:
        if args == ["--version"]:
            print(__version__)
            return 0
        parser, normalized = _parser(args)
        if not args or any(arg in ("--help", "-h", "help") for arg in args):
            print("Usage: arct <resource> <action> [ID] [flags]\n\nResources:")
            for resource in sorted(COMMANDS):
                print(f"  {resource:<12} {COMMANDS[resource]}")
            print()
            parser.print_help()
            print("\nARCT_TOKEN overrides saved credentials. Tokens are never accepted as flags.\nConfirm paid/destructive actions with --yes in automation. JSON hides passwords unless --show-password is explicit.")
            return 0
        f = vars(parser.parse_intermixed_args(normalized))
        pos = f.pop("positions")
        if len(pos) < 2 or pos[0] not in COMMANDS or pos[1] not in COMMANDS[pos[0]].split():
            raise UsageError("expected arct <resource> <action>; run arct --help")
        if f["output"] == "json" and (f.get("columns") or f.get("no_header")):
            raise UsageError("--columns and --no-header apply to table output")
        resource, action, *ids = pos
        result = app.local(resource, action, ids, f) if resource in ("auth", "context") else app.remote(resource, action, ids, f)
        app.render(result, f)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        return app.failure(error, json_mode)
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)
