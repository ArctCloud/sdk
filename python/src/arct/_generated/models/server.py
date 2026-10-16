from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, StrictStr, model_validator

from arct._generated.models.vm_status import VMStatus

class Server(BaseModel):
    model_config = ConfigDict(extra='allow', validate_assignment=True)
    id: UUID
    hostname: StrictStr
    status: VMStatus
    location: StrictStr
    plan: StrictStr
    plan_name: StrictStr | None
    cpu_cores: StrictInt
    ram_gb: StrictInt
    storage_gb: StrictInt
    bandwidth_tb: StrictInt
    ipv4: StrictStr | None
    ipv6: StrictStr | None
    os: StrictStr
    login_user: StrictStr | None
    labels: list[StrictStr]
    delete_protection: StrictBool
    billing_period: StrictStr
    price: Decimal
    next_due_date: date | None
    cancel_at: datetime | None
    created_at: datetime
