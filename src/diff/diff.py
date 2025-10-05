from diff import json_path
from diff.delta import Delta


def diff(new: dict, old: dict) -> list[Delta]:
    new_path_map = json_path.path_value_map(
        new, include_root=True, leaves_only=True, include_containers=False
    )
    old_path_map = json_path.path_value_map(
        old, include_root=True, leaves_only=False, include_containers=False
    )
    ops: list[Delta] = []

    # deleted
    deleted = old_path_map.keys() - new_path_map.keys()
    for item in deleted:
        ops.append(  # noqa: PERF401
            Delta(path=item, op="deleted", old_value=old_path_map[item], new_value=None)
        )

    # added
    added = new_path_map.keys() - old_path_map.keys()
    for item in added:
        ops.append(  # noqa: PERF401
            Delta(path=item, op="added", old_value=None, new_value=new_path_map[item])
        )

    # modified
    shared_keys = new_path_map.keys() & old_path_map.keys()
    for item in shared_keys:
        if old_path_map[item] != new_path_map[item]:
            ops.append(  # noqa: PERF401
                Delta(
                    path=item,
                    op="modified",
                    old_value=old_path_map[item],
                    new_value=new_path_map[item],
                )
            )
    # exlude root diff
    return ops
