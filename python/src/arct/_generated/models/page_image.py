from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator

from arct._generated.models.image import Image
from arct._generated.models.pagination import Pagination

class PageImage(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    data: list[Image]
    pagination: Pagination
