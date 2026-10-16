from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID
from decimal import Decimal
from pydantic import Field, StrictStr, StrictBool, StrictInt, TypeAdapter
from arct._types import UNSET, Unset
from arct._generated.models import *


class ServersApi:
    def __init__(self, client):
        self._client = client


    def cancel_deletion(self, server_id: UUID | str) -> Server:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return self._client.request("servers_cancel_deletion", "POST", f"/servers/{server_id}/cancel-deletion", query, body, Server)


    def create(self, *, hostname: Annotated[StrictStr, Field(max_length=63, pattern='^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$')], location: Annotated[StrictStr, Field(pattern='^[A-Za-z0-9-]{1,10}$')], plan: Annotated[StrictStr, Field(pattern='^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$')], image_id: UUID | str, billing_period: Literal['monthly', 'quarterly', 'semi_annual', 'yearly'] | Unset = UNSET, ssh_key_ids: Annotated[list[UUID | str], Field(max_length=20)] | Unset = UNSET, coupon_code: Annotated[StrictStr, Field(max_length=64, min_length=1)] | None | Unset = UNSET, enable_backups: StrictBool | Unset = UNSET) -> CreateServerResponse:
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = CreateServerRequest.model_validate({k: v for k, v in {'hostname': hostname, 'location': location, 'plan': plan, 'image_id': image_id, 'billing_period': billing_period, 'ssh_key_ids': ssh_key_ids, 'coupon_code': coupon_code, 'enable_backups': enable_backups}.items() if v is not UNSET}).model_dump(exclude_unset=True, mode='python')
        return self._client.request("servers_create", "POST", f"/servers", query, body, CreateServerResponse)


    def delete(self, server_id: UUID | str, *, at_period_end: StrictBool | Unset = UNSET) -> Server | None:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {'at_period_end': at_period_end}.items() if v is not UNSET and v is not None}
        if at_period_end is not UNSET and at_period_end is not None:
            query['at_period_end'] = TypeAdapter(StrictBool).validate_python(at_period_end)
        body = None
        return self._client.request("servers_delete", "DELETE", f"/servers/{server_id}", query, body, Server)


    def get(self, server_id: UUID | str) -> Server:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return self._client.request("servers_get", "GET", f"/servers/{server_id}", query, body, Server)


    def list_page(self, *, status: Literal['provisioning', 'running', 'stopped', 'restarting', 'reinstalling', 'restoring', 'deleting', 'suspended', 'pre_order'] | None | Unset = UNSET, location: Annotated[StrictStr, Field(pattern='^[A-Za-z0-9-]{1,10}$')] | None | Unset = UNSET, page: Annotated[StrictInt, Field(ge=1, le=100000)] | Unset = UNSET, per_page: Annotated[StrictInt, Field(ge=1, le=100)] | Unset = UNSET) -> PageServer:
        query = {k: v for k, v in {'status': status, 'location': location, 'page': page, 'per_page': per_page}.items() if v is not UNSET and v is not None}
        if status is not UNSET and status is not None:
            query['status'] = TypeAdapter(Literal['provisioning', 'running', 'stopped', 'restarting', 'reinstalling', 'restoring', 'deleting', 'suspended', 'pre_order'] | None).validate_python(status)
        if location is not UNSET and location is not None:
            query['location'] = TypeAdapter(Annotated[StrictStr, Field(pattern='^[A-Za-z0-9-]{1,10}$')] | None).validate_python(location)
        if page is not UNSET and page is not None:
            query['page'] = TypeAdapter(Annotated[StrictInt, Field(ge=1, le=100000)]).validate_python(page)
        if per_page is not UNSET and per_page is not None:
            query['per_page'] = TypeAdapter(Annotated[StrictInt, Field(ge=1, le=100)]).validate_python(per_page)
        body = None
        return self._client.request("servers_list", "GET", f"/servers", query, body, PageServer)


    def reinstall(self, server_id: UUID | str, *, image_id: UUID | str, ssh_key_ids: Annotated[list[UUID | str], Field(max_length=20)] | Unset = UNSET, hostname: Annotated[StrictStr, Field(max_length=63, min_length=1, pattern='^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$')] | Unset = UNSET) -> ReinstallResponse:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = ServerReinstall.model_validate({k: v for k, v in {'image_id': image_id, 'ssh_key_ids': ssh_key_ids, 'hostname': hostname}.items() if v is not UNSET}).model_dump(exclude_unset=True, mode='python')
        return self._client.request("servers_reinstall", "POST", f"/servers/{server_id}/reinstall", query, body, ReinstallResponse)


    def resize(self, server_id: UUID | str, *, plan: Annotated[StrictStr, Field(pattern='^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$')], expected_amount: Annotated[Decimal, Field(ge=0.0)] | StrictStr | None | Unset = UNSET) -> ResizeResponse:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = ResizeServerRequest.model_validate({k: v for k, v in {'plan': plan, 'expected_amount': expected_amount}.items() if v is not UNSET}).model_dump(exclude_unset=True, mode='python')
        return self._client.request("servers_resize", "POST", f"/servers/{server_id}/resize", query, body, ResizeResponse)


    def resize_options(self, server_id: UUID | str) -> ResizeOptions:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return self._client.request("servers_resize_options", "GET", f"/servers/{server_id}/resize-options", query, body, ResizeOptions)


    def restart(self, server_id: UUID | str) -> Server:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return self._client.request("servers_restart", "POST", f"/servers/{server_id}/restart", query, body, Server)


    def start(self, server_id: UUID | str) -> Server:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return self._client.request("servers_start", "POST", f"/servers/{server_id}/start", query, body, Server)


    def stop(self, server_id: UUID | str) -> Server:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return self._client.request("servers_stop", "POST", f"/servers/{server_id}/stop", query, body, Server)


    def update(self, server_id: UUID | str, *, hostname: Annotated[StrictStr, Field(max_length=63, min_length=1, pattern='^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$')] | Unset = UNSET, delete_protection: StrictBool | Unset = UNSET, labels: Annotated[list[Annotated[StrictStr, Field(max_length=63)]], Field(max_length=100)] | Unset = UNSET) -> Server:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = ServerUpdate.model_validate({k: v for k, v in {'hostname': hostname, 'delete_protection': delete_protection, 'labels': labels}.items() if v is not UNSET}).model_dump(exclude_unset=True, mode='python')
        return self._client.request("servers_update", "PATCH", f"/servers/{server_id}", query, body, Server)



class AsyncServersApi:
    def __init__(self, client):
        self._client = client


    async def cancel_deletion(self, server_id: UUID | str) -> Server:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return await self._client.request("servers_cancel_deletion", "POST", f"/servers/{server_id}/cancel-deletion", query, body, Server)


    async def create(self, *, hostname: Annotated[StrictStr, Field(max_length=63, pattern='^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$')], location: Annotated[StrictStr, Field(pattern='^[A-Za-z0-9-]{1,10}$')], plan: Annotated[StrictStr, Field(pattern='^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$')], image_id: UUID | str, billing_period: Literal['monthly', 'quarterly', 'semi_annual', 'yearly'] | Unset = UNSET, ssh_key_ids: Annotated[list[UUID | str], Field(max_length=20)] | Unset = UNSET, coupon_code: Annotated[StrictStr, Field(max_length=64, min_length=1)] | None | Unset = UNSET, enable_backups: StrictBool | Unset = UNSET) -> CreateServerResponse:
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = CreateServerRequest.model_validate({k: v for k, v in {'hostname': hostname, 'location': location, 'plan': plan, 'image_id': image_id, 'billing_period': billing_period, 'ssh_key_ids': ssh_key_ids, 'coupon_code': coupon_code, 'enable_backups': enable_backups}.items() if v is not UNSET}).model_dump(exclude_unset=True, mode='python')
        return await self._client.request("servers_create", "POST", f"/servers", query, body, CreateServerResponse)


    async def delete(self, server_id: UUID | str, *, at_period_end: StrictBool | Unset = UNSET) -> Server | None:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {'at_period_end': at_period_end}.items() if v is not UNSET and v is not None}
        if at_period_end is not UNSET and at_period_end is not None:
            query['at_period_end'] = TypeAdapter(StrictBool).validate_python(at_period_end)
        body = None
        return await self._client.request("servers_delete", "DELETE", f"/servers/{server_id}", query, body, Server)


    async def get(self, server_id: UUID | str) -> Server:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return await self._client.request("servers_get", "GET", f"/servers/{server_id}", query, body, Server)


    async def list_page(self, *, status: Literal['provisioning', 'running', 'stopped', 'restarting', 'reinstalling', 'restoring', 'deleting', 'suspended', 'pre_order'] | None | Unset = UNSET, location: Annotated[StrictStr, Field(pattern='^[A-Za-z0-9-]{1,10}$')] | None | Unset = UNSET, page: Annotated[StrictInt, Field(ge=1, le=100000)] | Unset = UNSET, per_page: Annotated[StrictInt, Field(ge=1, le=100)] | Unset = UNSET) -> PageServer:
        query = {k: v for k, v in {'status': status, 'location': location, 'page': page, 'per_page': per_page}.items() if v is not UNSET and v is not None}
        if status is not UNSET and status is not None:
            query['status'] = TypeAdapter(Literal['provisioning', 'running', 'stopped', 'restarting', 'reinstalling', 'restoring', 'deleting', 'suspended', 'pre_order'] | None).validate_python(status)
        if location is not UNSET and location is not None:
            query['location'] = TypeAdapter(Annotated[StrictStr, Field(pattern='^[A-Za-z0-9-]{1,10}$')] | None).validate_python(location)
        if page is not UNSET and page is not None:
            query['page'] = TypeAdapter(Annotated[StrictInt, Field(ge=1, le=100000)]).validate_python(page)
        if per_page is not UNSET and per_page is not None:
            query['per_page'] = TypeAdapter(Annotated[StrictInt, Field(ge=1, le=100)]).validate_python(per_page)
        body = None
        return await self._client.request("servers_list", "GET", f"/servers", query, body, PageServer)


    async def reinstall(self, server_id: UUID | str, *, image_id: UUID | str, ssh_key_ids: Annotated[list[UUID | str], Field(max_length=20)] | Unset = UNSET, hostname: Annotated[StrictStr, Field(max_length=63, min_length=1, pattern='^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$')] | Unset = UNSET) -> ReinstallResponse:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = ServerReinstall.model_validate({k: v for k, v in {'image_id': image_id, 'ssh_key_ids': ssh_key_ids, 'hostname': hostname}.items() if v is not UNSET}).model_dump(exclude_unset=True, mode='python')
        return await self._client.request("servers_reinstall", "POST", f"/servers/{server_id}/reinstall", query, body, ReinstallResponse)


    async def resize(self, server_id: UUID | str, *, plan: Annotated[StrictStr, Field(pattern='^[A-Za-z0-9][A-Za-z0-9_.-]{0,49}$')], expected_amount: Annotated[Decimal, Field(ge=0.0)] | StrictStr | None | Unset = UNSET) -> ResizeResponse:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = ResizeServerRequest.model_validate({k: v for k, v in {'plan': plan, 'expected_amount': expected_amount}.items() if v is not UNSET}).model_dump(exclude_unset=True, mode='python')
        return await self._client.request("servers_resize", "POST", f"/servers/{server_id}/resize", query, body, ResizeResponse)


    async def resize_options(self, server_id: UUID | str) -> ResizeOptions:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return await self._client.request("servers_resize_options", "GET", f"/servers/{server_id}/resize-options", query, body, ResizeOptions)


    async def restart(self, server_id: UUID | str) -> Server:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return await self._client.request("servers_restart", "POST", f"/servers/{server_id}/restart", query, body, Server)


    async def start(self, server_id: UUID | str) -> Server:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return await self._client.request("servers_start", "POST", f"/servers/{server_id}/start", query, body, Server)


    async def stop(self, server_id: UUID | str) -> Server:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return await self._client.request("servers_stop", "POST", f"/servers/{server_id}/stop", query, body, Server)


    async def update(self, server_id: UUID | str, *, hostname: Annotated[StrictStr, Field(max_length=63, min_length=1, pattern='^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$')] | Unset = UNSET, delete_protection: StrictBool | Unset = UNSET, labels: Annotated[list[Annotated[StrictStr, Field(max_length=63)]], Field(max_length=100)] | Unset = UNSET) -> Server:
        server_id = UUID(str(server_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = ServerUpdate.model_validate({k: v for k, v in {'hostname': hostname, 'delete_protection': delete_protection, 'labels': labels}.items() if v is not UNSET}).model_dump(exclude_unset=True, mode='python')
        return await self._client.request("servers_update", "PATCH", f"/servers/{server_id}", query, body, Server)
