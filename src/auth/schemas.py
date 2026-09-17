from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CallerRole = Literal["user", "worker", "admin"]


@dataclass(frozen=True)
class Caller:
    subject_id: str
    role: CallerRole
