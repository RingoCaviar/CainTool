from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


DrawFunction = Callable[[object, object], None]


@dataclass(frozen=True)
class FeatureSection:
    key: str
    label: str
    icon: str
    description: str
    draw: DrawFunction
    enabled: bool = True
