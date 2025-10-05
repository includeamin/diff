import dataclasses
import typing


@dataclasses.dataclass
class Operation:
    op: typing.Literal["deleted", "modified", "added"]
    path: str
    new_value: typing.Any | None
    old_value: typing.Any | None
