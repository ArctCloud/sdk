from __future__ import annotations

import warnings
from typing import Annotated, Any, Literal
from uuid import UUID
from decimal import Decimal
from pydantic import Field, StrictStr, StrictBool, StrictInt, TypeAdapter
from arct._types import UNSET, Unset
from arct._generated.models import *


class ImagesApi:
    def __init__(self, client):
        self._client = client


    def list_page(self, *, location: Annotated[StrictStr, Field(pattern='^[A-Za-z0-9-]{1,10}$')] | None | Unset = UNSET, datacenter: Annotated[StrictStr, Field(pattern='^[A-Za-z]{2,5}[0-9]{1,2}$')] | None | Unset = UNSET, page: Annotated[StrictInt, Field(ge=1, le=100000)] | Unset = UNSET, per_page: Annotated[StrictInt, Field(ge=1, le=100)] | Unset = UNSET) -> PageImage:
        query = {k: v for k, v in {'location': location, 'datacenter': datacenter, 'page': page, 'per_page': per_page}.items() if v is not UNSET and v is not None}
        if location is not UNSET and location is not None:
            query['location'] = TypeAdapter(Annotated[StrictStr, Field(pattern='^[A-Za-z0-9-]{1,10}$')] | None).validate_python(location)
        if datacenter is not UNSET and datacenter is not None:
            query['datacenter'] = TypeAdapter(Annotated[StrictStr, Field(pattern='^[A-Za-z]{2,5}[0-9]{1,2}$')] | None).validate_python(datacenter)
        if page is not UNSET and page is not None:
            query['page'] = TypeAdapter(Annotated[StrictInt, Field(ge=1, le=100000)]).validate_python(page)
        if per_page is not UNSET and per_page is not None:
            query['per_page'] = TypeAdapter(Annotated[StrictInt, Field(ge=1, le=100)]).validate_python(per_page)
        body = None
        if location is not UNSET and location is not None:
            warnings.warn('location is deprecated; use datacenter instead', DeprecationWarning, stacklevel=2)
        return self._client.request("images_list", "GET", f"/images", query, body, PageImage)



class AsyncImagesApi:
    def __init__(self, client):
        self._client = client


    async def list_page(self, *, location: Annotated[StrictStr, Field(pattern='^[A-Za-z0-9-]{1,10}$')] | None | Unset = UNSET, datacenter: Annotated[StrictStr, Field(pattern='^[A-Za-z]{2,5}[0-9]{1,2}$')] | None | Unset = UNSET, page: Annotated[StrictInt, Field(ge=1, le=100000)] | Unset = UNSET, per_page: Annotated[StrictInt, Field(ge=1, le=100)] | Unset = UNSET) -> PageImage:
        query = {k: v for k, v in {'location': location, 'datacenter': datacenter, 'page': page, 'per_page': per_page}.items() if v is not UNSET and v is not None}
        if location is not UNSET and location is not None:
            query['location'] = TypeAdapter(Annotated[StrictStr, Field(pattern='^[A-Za-z0-9-]{1,10}$')] | None).validate_python(location)
        if datacenter is not UNSET and datacenter is not None:
            query['datacenter'] = TypeAdapter(Annotated[StrictStr, Field(pattern='^[A-Za-z]{2,5}[0-9]{1,2}$')] | None).validate_python(datacenter)
        if page is not UNSET and page is not None:
            query['page'] = TypeAdapter(Annotated[StrictInt, Field(ge=1, le=100000)]).validate_python(page)
        if per_page is not UNSET and per_page is not None:
            query['per_page'] = TypeAdapter(Annotated[StrictInt, Field(ge=1, le=100)]).validate_python(per_page)
        body = None
        if location is not UNSET and location is not None:
            warnings.warn('location is deprecated; use datacenter instead', DeprecationWarning, stacklevel=2)
        return await self._client.request("images_list", "GET", f"/images", query, body, PageImage)
