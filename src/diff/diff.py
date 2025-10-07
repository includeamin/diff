import typing

from diff import json_path
from diff.delta import Delta


def diff(new: dict[str, typing.Any], old: dict[str, typing.Any]) -> list[Delta]:
    new_path_map = json_path.path_value_map(
        new, include_root=True, leaves_only=True, include_containers=False
    )
    old_path_map = json_path.path_value_map(
        old, include_root=True, leaves_only=False, include_containers=False
    )
    operations: list[Delta] = []

    deleted = old_path_map.keys() - new_path_map.keys()
    for key in deleted:
        operations.append(  # noqa: PERF401
            Delta(
                path=key,
                operation="deleted",
                old_value=old_path_map[key],
                new_value=None,
            )
        )

    added = new_path_map.keys() - old_path_map.keys()
    for key in added:
        operations.append(  # noqa: PERF401
            Delta(
                path=key, operation="added", old_value=None, new_value=new_path_map[key]
            )
        )

    shared_keys = new_path_map.keys() & old_path_map.keys()
    for key in shared_keys:
        if old_path_map[key] != new_path_map[key]:
            operations.append(  # noqa: PERF401
                Delta(
                    path=key,
                    operation="modified",
                    old_value=old_path_map[key],
                    new_value=new_path_map[key],
                )
            )
    return operations
