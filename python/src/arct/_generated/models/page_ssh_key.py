from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator

from arct._generated.models.pagination import Pagination
from arct._generated.models.ssh_key import SshKey

class PageSshKey(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    data: list[SshKey]
    pagination: Pagination
