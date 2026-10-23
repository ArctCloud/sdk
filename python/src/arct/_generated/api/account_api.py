from __future__ import annotations

import warnings
from typing import Annotated, Any, Literal
from uuid import UUID
from decimal import Decimal
from pydantic import Field, StrictStr, StrictBool, StrictInt, TypeAdapter
from arct._types import UNSET, Unset
from arct._generated.models import *


class AccountApi:
    def __init__(self, client):
        self._client = client


    def get(self) -> Account:
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return self._client.request("account_get", "GET", f"/account", query, body, Account)



class AsyncAccountApi:
    def __init__(self, client):
        self._client = client


    async def get(self) -> Account:
        query = {k: v for k, v in {}.items() if v is not UNSET and v is not None}
        body = None
        return await self._client.request("account_get", "GET", f"/account", query, body, Account)
