import asyncio
from contextvars import ContextVar
from datetime import datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
import json
import math
import os
import random
import time
from urllib.parse import urlparse
from uuid import UUID

import httpx
from pydantic import SecretStr, ValidationError as ModelValidationError

from . import _limits
from .errors import APIError, ChargeUnknownError, UncertainOperationError, WaitTimeoutError, from_response

_DEADLINE = ContextVar("arct_deadline", default=None)


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise WaitTimeoutError()
    return value


def json_default(value):
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    raise TypeError("Unsupported JSON value")


def retry_delay(response, attempt):
    header = response.headers.get("retry-after") if response is not None else None
    if header:
        try:
            value = float(header)
        except ValueError:
            try:
                value = (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                value = 0
        if math.isfinite(value):
            return max(0, value)
    return 0.5 * 2 ** attempt + random.uniform(0, 0.25)


def buffered_response(response, content, deadline, *, encoded=False):
    remaining(deadline)
    headers = [(key, value) for key, value in response.headers.multi_items() if key != "content-length" and (encoded or key != "content-encoding")]
    value = httpx.Response(response.status_code, headers=headers, content=content, request=response.request)
    remaining(deadline)
    return value


class Transport:
    def __init__(self, *, token=None, base_url="https://api.arct.cloud/v1", transport=None, timeout=30.0, operation_timeout=600.0, asynchronous=False):
        value = token if token is not None else os.environ.get("ARCT_TOKEN")
        if not isinstance(value, str) or not value:
            raise ValueError("Set ARCT_TOKEN or pass token")
        if any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ValueError("token must contain printable ASCII without whitespace")
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        if not math.isfinite(operation_timeout) or operation_timeout <= 0:
            raise ValueError("operation_timeout must be finite and positive")
        url = urlparse(base_url)
        if url.username or url.password or url.query or url.fragment or not url.hostname or (url.scheme != "https" and not (url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1"))):
            raise ValueError("base_url requires HTTPS except localhost")
        self.token = SecretStr(value)
        self.key = _limits.token_key(value)
        self.timeout = float(timeout)
        self.operation_timeout = float(operation_timeout)
        client = httpx.AsyncClient if asynchronous else httpx.Client
        self.http = client(base_url=base_url.rstrip("/") + "/", headers={"Authorization": f"Bearer {value}", "User-Agent": "arct-cloud-python/0.1.0"}, timeout=timeout, follow_redirects=False, transport=transport)
        self.asynchronous = asynchronous

    def __repr__(self):
        return f"Transport(token={self.token!r})"

    def deadline(self):
        return min(_DEADLINE.get() or float("inf"), time.monotonic() + self.operation_timeout)

    def parse(self, response, model, op, query):
        if not 200 <= response.status_code < 300:
            raise from_response(response, self.token.get_secret_value())
        if response.status_code == 204:
            if op == "ssh_keys_delete" or (op == "servers_delete" and query.get("at_period_end") is not True):
                return None
            raise APIError("API returned an unexpected empty response", status=204, code="invalid_response")
        if model is None:
            return None
        try:
            data = json.loads(response.content, parse_float=Decimal)
            value = model.model_validate(data)
        except (ValueError, ModelValidationError):
            raise APIError("API returned an invalid response", status=response.status_code, code="invalid_response") from None
        if op == "account_get":
            _limits.bind(self.key, value.id)
        if op in ("servers_restart", "servers_reinstall"):
            value.__dict__["_arct_action"] = op
            if op == "servers_reinstall":
                value.server.__dict__["_arct_action"] = op
        return value

    def decision(self, response, error, op, attempt, promo_used):
        if isinstance(error, ChargeUnknownError):
            return False
        if response is not None and response.status_code == 429:
            return attempt < 2
        if op == "servers_create" and error.code == "promo_changed" and not promo_used:
            return attempt < 2
        transient = response is None or response.status_code in (500, 503)
        if transient and (op.endswith("_get") or op.endswith("_list") or op == "servers_resize_options" or op == "servers_create"):
            return attempt < 2
        return False

    def uncertain(self, response, error, method, op):
        if isinstance(error, ChargeUnknownError):
            return error
        if method != "GET" and op != "servers_create" and (response is None or response.status_code in (500, 503) or error.code == "invalid_response"):
            return UncertainOperationError("The operation may have been accepted; inspect current state before repeating it", status=error.status, code="operation_uncertain", details=error.details)
        if op == "servers_create" and (response is None or response.status_code in (500, 503) or error.code == "invalid_response"):
            return UncertainOperationError("Creation completion is unknown; inspect servers before creating again", status=error.status, code="create_uncertain", details=error.details)
        return error

    def request(self, op, method, path, query, body, model):
        if self.asynchronous:
            return self.arequest(op, method, path, query, body, model)
        token = _DEADLINE.set(self.deadline())
        state = {}
        try:
            return self._request(op, method, path, query, body, model, state)
        except TimeoutError:
            raise self.deadline_error(op, state) from None
        finally:
            _DEADLINE.reset(token)

    def _request(self, op, method, path, query, body, model, state):
        deadline = _DEADLINE.get()
        started = datetime.now(timezone.utc)
        if method != "GET" and not _limits.account_for(self.key):
            from ._generated.api.account_api import AccountApi
            AccountApi(self).get()
        content = json.dumps(body, default=json_default, separators=(",", ":")).encode() if body is not None else None
        promo_used = False
        for attempt in range(3):
            while True:
                remaining(deadline)
                delay = _limits.reserve(self.key, _limits.account_for(self.key), method, op in ("servers_create", "servers_resize"))
                if not delay:
                    break
                self.sleep(delay, deadline)
            response = None
            try:
                with self.http.stream(method, path.lstrip("/"), params=query, content=content, headers={"Content-Type": "application/json"} if content is not None else None, timeout=min(self.timeout, remaining(deadline))) as streamed:
                    if streamed.is_stream_consumed:
                        response = buffered_response(streamed, streamed.content, deadline)
                    else:
                        chunks = []
                        for chunk in streamed.iter_raw():
                            remaining(deadline)
                            chunks.append(chunk)
                        response = buffered_response(streamed, b"".join(chunks), deadline, encoded=True)
                value = self.parse(response, model, op, query)
                remaining(deadline)
                if op == "servers_create":
                    value.__dict__["_arct_hostname"] = body["hostname"]
                return value
            except httpx.DecodingError:
                error = APIError("API returned an undecodable response", code="invalid_response")
                raise self.uncertain(response, error, method, op) from None
            except (httpx.TransportError, TimeoutError) as caught:
                state["ambiguous"] = state.get("ambiguous", False) or method != "GET"
                if isinstance(caught, TimeoutError):
                    raise
                error = APIError("Network request failed", code="network_error")
            except APIError as caught:
                state["ambiguous"] = state.get("ambiguous", False) or (method != "GET" and response is not None and response.status_code >= 500)
                error = caught
            if op == "servers_create" and attempt and error.code == "hostname_taken" and not isinstance(error, ChargeUnknownError):
                candidates = self.reconcile(body, error.details)
                error.details["candidate_checks"] = self.candidate_checks(body, candidates, started)
                raise UncertainOperationError("A matching hostname exists, but order ownership and the one-time password cannot be recovered", status=409, code="create_uncertain", details=error.details, candidates=candidates) from None
            if not self.decision(response, error, op, attempt, promo_used):
                raise self.uncertain(response, error, method, op) from None
            promo_used = promo_used or error.code == "promo_changed"
            self.sleep(retry_delay(response, attempt), deadline)

    def deadline_error(self, op, state):
        if state.get("ambiguous"):
            return UncertainOperationError("The deadline expired after a mutation; inspect current state before repeating it", code="create_uncertain" if op == "servers_create" else "operation_uncertain", details={"deadline_exceeded": True})
        return WaitTimeoutError()

    def sleep(self, delay, deadline):
        time.sleep(min(delay, remaining(deadline)))
        remaining(deadline)

    async def asleep(self, delay, deadline):
        await asyncio.sleep(min(delay, remaining(deadline)))
        remaining(deadline)

    async def arequest(self, op, method, path, query, body, model):
        token = _DEADLINE.set(self.deadline())
        state = {}
        try:
            return await self._arequest(op, method, path, query, body, model, state)
        except TimeoutError:
            raise self.deadline_error(op, state) from None
        finally:
            _DEADLINE.reset(token)

    async def _arequest(self, op, method, path, query, body, model, state):
        deadline = _DEADLINE.get()
        started = datetime.now(timezone.utc)
        if method != "GET" and not _limits.account_for(self.key):
            from ._generated.api.account_api import AsyncAccountApi
            await AsyncAccountApi(self).get()
        content = json.dumps(body, default=json_default, separators=(",", ":")).encode() if body is not None else None
        promo_used = False
        for attempt in range(3):
            while True:
                remaining(deadline)
                delay = _limits.reserve(self.key, _limits.account_for(self.key), method, op in ("servers_create", "servers_resize"))
                if not delay:
                    break
                await self.asleep(delay, deadline)
            response = None
            try:
                async with asyncio.timeout(remaining(deadline)):
                    async with self.http.stream(method, path.lstrip("/"), params=query, content=content, headers={"Content-Type": "application/json"} if content is not None else None, timeout=min(self.timeout, remaining(deadline))) as streamed:
                        if streamed.is_stream_consumed:
                            response = buffered_response(streamed, streamed.content, deadline)
                        else:
                            chunks = []
                            async for chunk in streamed.aiter_raw():
                                remaining(deadline)
                                chunks.append(chunk)
                            response = buffered_response(streamed, b"".join(chunks), deadline, encoded=True)
                value = self.parse(response, model, op, query)
                remaining(deadline)
                if op == "servers_create":
                    value.__dict__["_arct_hostname"] = body["hostname"]
                return value
            except httpx.DecodingError:
                error = APIError("API returned an undecodable response", code="invalid_response")
                raise self.uncertain(response, error, method, op) from None
            except (httpx.TransportError, TimeoutError) as caught:
                state["ambiguous"] = state.get("ambiguous", False) or method != "GET"
                if isinstance(caught, TimeoutError):
                    raise
                error = APIError("Network request failed", code="network_error")
            except APIError as caught:
                state["ambiguous"] = state.get("ambiguous", False) or (method != "GET" and response is not None and response.status_code >= 500)
                error = caught
            if op == "servers_create" and attempt and error.code == "hostname_taken" and not isinstance(error, ChargeUnknownError):
                candidates = await self.areconcile(body, error.details)
                error.details["candidate_checks"] = self.candidate_checks(body, candidates, started)
                raise UncertainOperationError("A matching hostname exists, but order ownership and the one-time password cannot be recovered", status=409, code="create_uncertain", details=error.details, candidates=candidates) from None
            if not self.decision(response, error, op, attempt, promo_used):
                raise self.uncertain(response, error, method, op) from None
            promo_used = promo_used or error.code == "promo_changed"
            await self.asleep(retry_delay(response, attempt), deadline)

    def candidate_checks(self, body, candidates, started):
        return [{"server_id": str(v.id), "attributes_match": v.hostname == body["hostname"] and v.location.lower() == body["location"].lower() and v.plan == body["plan"] and v.billing_period == body.get("billing_period", "monthly"), "created_since_attempt": v.created_at.replace(tzinfo=v.created_at.tzinfo or timezone.utc) >= started} for v in candidates]

    def reconcile(self, body, details):
        try:
            return self._reconcile(body, details)
        except ChargeUnknownError:
            raise
        except APIError as error:
            details["discovery_error"] = error.code
            return []

    def _reconcile(self, body, details):
        from ._generated.api.servers_api import ServersApi
        api = ServersApi(self)
        if details.get("server_id"):
            try:
                return [api.get(details["server_id"])]
            except ValueError:
                return []
        candidates = []
        page = 1
        while True:
            value = api.list_page(page=page, per_page=100)
            candidates.extend(v for v in value.data if v.hostname == body["hostname"])
            if not value.data or page >= value.pagination.total_pages:
                return candidates
            page += 1

    async def areconcile(self, body, details):
        try:
            return await self._areconcile(body, details)
        except ChargeUnknownError:
            raise
        except APIError as error:
            details["discovery_error"] = error.code
            return []

    async def _areconcile(self, body, details):
        from ._generated.api.servers_api import AsyncServersApi
        api = AsyncServersApi(self)
        if details.get("server_id"):
            try:
                return [await api.get(details["server_id"])]
            except ValueError:
                return []
        candidates = []
        page = 1
        while True:
            value = await api.list_page(page=page, per_page=100)
            candidates.extend(v for v in value.data if v.hostname == body["hostname"])
            if not value.data or page >= value.pagination.total_pages:
                return candidates
            page += 1
