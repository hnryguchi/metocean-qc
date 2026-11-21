# © 2026 Henry Noguchi (github.com/hnryguchi). Todos os direitos reservados / All rights reserved. Ver/see LICENSE.
"""Core data structures: time series, QC flags and findings."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum


class Flag(IntEnum):
    """Per-value quality flags, following the IOOS QARTOD flag scheme.

    QARTOD: https://ioos.noaa.gov/project/qartod/ . This project borrows the flag
    values and test families; it is not a certified QARTOD implementation.
    """

    GOOD = 1
    NOT_EVALUATED = 2
    SUSPECT = 3
    FAIL = 4
    MISSING = 9


@dataclass
class Series:
    """One station: timestamps (UTC, ascending) and one value list per variable.

    Missing values are ``None``. All value lists have the same length as ``times``.
    """

    station: str
    times: list[datetime]
    values: dict[str, list[float | None]]
    units: dict[str, str] = field(default_factory=dict)
    source: str = ""

    def __post_init__(self) -> None:
        for name, column in self.values.items():
            if len(column) != len(self.times):
                raise ValueError(
                    f"variable {name!r} has {len(column)} values for {len(self.times)} timestamps"
                )

    @property
    def variables(self) -> list[str]:
        return list(self.values)


@dataclass(frozen=True)
class Finding:
    """One rule result on one value (or one interval, for gaps)."""

    variable: str
    index: int
    time: datetime
    test: str
    flag: Flag
    value: float | None
    detail: str
