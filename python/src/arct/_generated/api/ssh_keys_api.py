from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID
from decimal import Decimal
from pydantic import Field, StrictStr, StrictBool, StrictInt, TypeAdapter
from arct._types import UNSET, Unset
from arct._generated.models import *


class SshKeysApi:
    def __init__(self, client):
        self._client = client


    def create(self, *, name: Annotated[StrictStr, Field(max_length=255, min_length=1)], public_key: Annotated[StrictStr, Field(max_length=8192, min_length=1)]) -> SshKey:
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = SshKeyCreate.model_validate({k: v for k, v in {'name': name, 'public_key': public_key}.items() if v is not UNSET}).model_dump(exclude_unset=True, mode='python')
        return self._client.request("ssh_keys_create", "POST", f"/ssh-keys", query, body, SshKey)


    def delete(self, key_id: UUID | str) -> None:
        key_id = UUID(str(key_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return self._client.request("ssh_keys_delete", "DELETE", f"/ssh-keys/{key_id}", query, body, None)


    def get(self, key_id: UUID | str) -> SshKey:
        key_id = UUID(str(key_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return self._client.request("ssh_keys_get", "GET", f"/ssh-keys/{key_id}", query, body, SshKey)


    def list_page(self, *, page: Annotated[StrictInt, Field(ge=1, le=100000)] | Unset = UNSET, per_page: Annotated[StrictInt, Field(ge=1, le=100)] | Unset = UNSET) -> PageSshKey:
        query = {k: v for k, v in {'page': page, 'per_page': per_page}.items() if v is not UNSET and v is not None}
        if page is not UNSET and page is not None:
            query['page'] = TypeAdapter(Annotated[StrictInt, Field(ge=1, le=100000)]).validate_python(page)
        if per_page is not UNSET and per_page is not None:
            query['per_page'] = TypeAdapter(Annotated[StrictInt, Field(ge=1, le=100)]).validate_python(per_page)
        body = None
        return self._client.request("ssh_keys_list", "GET", f"/ssh-keys", query, body, PageSshKey)



class AsyncSshKeysApi:
    def __init__(self, client):
        self._client = client


    async def create(self, *, name: Annotated[StrictStr, Field(max_length=255, min_length=1)], public_key: Annotated[StrictStr, Field(max_length=8192, min_length=1)]) -> SshKey:
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = SshKeyCreate.model_validate({k: v for k, v in {'name': name, 'public_key': public_key}.items() if v is not UNSET}).model_dump(exclude_unset=True, mode='python')
        return await self._client.request("ssh_keys_create", "POST", f"/ssh-keys", query, body, SshKey)


    async def delete(self, key_id: UUID | str) -> None:
        key_id = UUID(str(key_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return await self._client.request("ssh_keys_delete", "DELETE", f"/ssh-keys/{key_id}", query, body, None)


    async def get(self, key_id: UUID | str) -> SshKey:
        key_id = UUID(str(key_id))
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return await self._client.request("ssh_keys_get", "GET", f"/ssh-keys/{key_id}", query, body, SshKey)


    async def list_page(self, *, page: Annotated[StrictInt, Field(ge=1, le=100000)] | Unset = UNSET, per_page: Annotated[StrictInt, Field(ge=1, le=100)] | Unset = UNSET) -> PageSshKey:
        query = {k: v for k, v in {'page': page, 'per_page': per_page}.items() if v is not UNSET and v is not None}
        if page is not UNSET and page is not None:
            query['page'] = TypeAdapter(Annotated[StrictInt, Field(ge=1, le=100000)]).validate_python(page)
        if per_page is not UNSET and per_page is not None:
            query['per_page'] = TypeAdapter(Annotated[StrictInt, Field(ge=1, le=100)]).validate_python(per_page)
        body = None
        return await self._client.request("ssh_keys_list", "GET", f"/ssh-keys", query, body, PageSshKey)
