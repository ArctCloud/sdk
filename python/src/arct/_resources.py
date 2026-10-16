from contextlib import contextmanager
import math
import time
from uuid import UUID

from ._generated.api.servers_api import ServersApi, AsyncServersApi
from ._generated.models import CreateServerResponse, ReinstallResponse, ResizeResponse, Server
from ._transport import _DEADLINE, remaining
from ._types import UNSET
from .errors import ConflictError, OperationFailedError, UncertainOperationError, WaitTimeoutError


class Pagination:
    def list(self, *, page=1, per_page=100, **filters):
        while True:
            value = self.list_page(page=page, per_page=per_page, **filters)
            yield from value.data
            if not value.data or page >= value.pagination.total_pages:
                return
            page += 1


class AsyncPagination:
    async def list(self, *, page=1, per_page=100, **filters):
        while True:
            value = await self.list_page(page=page, per_page=per_page, **filters)
            for item in value.data:
                yield item
            if not value.data or page >= value.pagination.total_pages:
                return
            page += 1


def quote_amount(options, plan):
    selected = next((p for p in options.plans if p.slug == plan), None)
    if not options.can_resize or selected is None or not selected.eligible or selected.amount_due_today is None:
        raise ConflictError("The selected plan is not eligible for resize", code=options.blocked_code or "ineligible")
    return selected.amount_due_today


@contextmanager
def deadline_scope(timeout, poll_interval=None):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    if poll_interval is not None and (not math.isfinite(poll_interval) or not 5 <= poll_interval <= 10):
        raise ValueError("poll_interval must be between 5 and 10 seconds")
    deadline = min(_DEADLINE.get() or float("inf"), time.monotonic() + timeout)
    token = _DEADLINE.set(deadline)
    try:
        yield deadline
    finally:
        _DEADLINE.reset(token)


def wait_input(value):
    action = getattr(value, "__dict__", {}).get("_arct_action")
    hostname = getattr(value, "__dict__", {}).get("_arct_hostname")
    if isinstance(value, CreateServerResponse):
        return value.server.id if value.server else value.order.server_id, value.server, False, hostname
    if isinstance(value, ReinstallResponse):
        return value.server.id, value.server, action is not None, hostname
    if isinstance(value, Server):
        return value.id, value, action is not None, hostname
    return UUID(str(value)), None, False, None


def observed(state, target, transition):
    if state.status in ("error", "suspended", "deleting") and state.status != target:
        raise OperationFailedError(state)
    return state.status == target and transition


class Servers(Pagination, ServersApi):
    def resize(self, server_id, *, plan, expected_amount=UNSET):
        with deadline_scope(self._client.operation_timeout):
            if expected_amount is UNSET:
                expected_amount = quote_amount(self.resize_options(server_id), plan)
            return super().resize(server_id, plan=plan, expected_amount=expected_amount)

    def wait_until(self, value, target_status, timeout=600, *, poll_interval=5):
        identifier, last, needs_transition, hostname = wait_input(value)
        transitioned = not needs_transition or (last is not None and last.status != target_status)
        with deadline_scope(timeout, poll_interval) as deadline:
            try:
                while True:
                    remaining(deadline)
                    if identifier is None:
                        matches = [s for s in self.list() if hostname and s.hostname == hostname]
                        if len(matches) > 1:
                            raise UncertainOperationError("Multiple servers match the acknowledged creation", code="discovery_uncertain", candidates=matches)
                        if matches:
                            identifier = matches[0].id
                    if identifier is not None:
                        last = self.get(identifier)
                        transitioned = transitioned or last.status != target_status
                        if observed(last, target_status, transitioned):
                            return last
                    self._client.sleep(poll_interval, deadline)
            except WaitTimeoutError:
                label = "Pre-order is still pending" if last is not None and last.status == "pre_order" else "Server completion remains unverified"
                raise WaitTimeoutError(label, last_state=last) from None

    def wait_resize(self, server_id, value, timeout=600, *, poll_interval=5):
        if not isinstance(value, ResizeResponse):
            raise TypeError("value must be a ResizeResponse")
        last = value
        with deadline_scope(timeout, poll_interval) as deadline:
            try:
                while True:
                    options = self.resize_options(server_id)
                    last = options
                    if options.pending_resize is None and options.current_plan == value.to_plan:
                        last = self.get(server_id)
                        if last.plan == value.to_plan:
                            return last
                    self._client.sleep(poll_interval, deadline)
            except WaitTimeoutError:
                raise WaitTimeoutError("Resize completion remains unverified; payment may be pending", last_state=last) from None


class AsyncServers(AsyncPagination, AsyncServersApi):
    async def resize(self, server_id, *, plan, expected_amount=UNSET):
        with deadline_scope(self._client.operation_timeout):
            if expected_amount is UNSET:
                expected_amount = quote_amount(await self.resize_options(server_id), plan)
            return await super().resize(server_id, plan=plan, expected_amount=expected_amount)

    async def wait_until(self, value, target_status, timeout=600, *, poll_interval=5):
        identifier, last, needs_transition, hostname = wait_input(value)
        transitioned = not needs_transition or (last is not None and last.status != target_status)
        with deadline_scope(timeout, poll_interval) as deadline:
            try:
                while True:
                    remaining(deadline)
                    if identifier is None:
                        matches = [s async for s in self.list() if hostname and s.hostname == hostname]
                        if len(matches) > 1:
                            raise UncertainOperationError("Multiple servers match the acknowledged creation", code="discovery_uncertain", candidates=matches)
                        if matches:
                            identifier = matches[0].id
                    if identifier is not None:
                        last = await self.get(identifier)
                        transitioned = transitioned or last.status != target_status
                        if observed(last, target_status, transitioned):
                            return last
                    await self._client.asleep(poll_interval, deadline)
            except WaitTimeoutError:
                label = "Pre-order is still pending" if last is not None and last.status == "pre_order" else "Server completion remains unverified"
                raise WaitTimeoutError(label, last_state=last) from None

    async def wait_resize(self, server_id, value, timeout=600, *, poll_interval=5):
        if not isinstance(value, ResizeResponse):
            raise TypeError("value must be a ResizeResponse")
        last = value
        with deadline_scope(timeout, poll_interval) as deadline:
            try:
                while True:
                    options = await self.resize_options(server_id)
                    last = options
                    if options.pending_resize is None and options.current_plan == value.to_plan:
                        last = await self.get(server_id)
                        if last.plan == value.to_plan:
                            return last
                    await self._client.asleep(poll_interval, deadline)
            except WaitTimeoutError:
                raise WaitTimeoutError("Resize completion remains unverified; payment may be pending", last_state=last) from None
