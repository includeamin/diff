import dataclasses
import typing


@dataclasses.dataclass
class Delta:
    operation: typing.Literal["deleted", "modified", "added"]
    path: str
    new_value: typing.Any | None
    old_value: typing.Any | None

    def __repr__(self):
        return (
            f"Delta(operation='{self.operation}', path='{self.path}', "
            f"new_value={self.new_value!r}, old_value={self.old_value!r})"
        )
