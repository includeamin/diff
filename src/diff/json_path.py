from typing import Any, Iterator, List, Tuple, Union, Optional

Token = Union[str, int]  # str for dict keys, int for list indices


def _escape_key_for_brackets(key: str) -> str:
    """Escape a key for bracket notation with double quotes."""
    return key.replace("\\", "\\\\").replace('"', '\\"')


def _join_path(base: str, token: Token) -> str:
    """
    Join a base path string with a token (dict key or list index) using a JSONPath-like syntax:
    - dict keys with no '.' or '[' use dot notation
    - otherwise keys are quoted: ["..."]
    - list indices use [i]
    The base may be '' or '$' or a full path.
    """
    if isinstance(token, int):
        return f"{base}[{token}]"

    key = token
    # Use dot-notation if it doesn't break the tokenizer used earlier.
    use_dot = (key != "") and ("." not in key) and ("[" not in key)
    if use_dot:
        if not base or base == "$":
            # "$" -> "$.key", "" -> "key"
            return (base + "." if base == "$" else "") + key
        return base + "." + key
    else:
        return f'{base}["{_escape_key_for_brackets(key)}"]'


def iter_json_paths(
    obj: Any,
    *,
    include_root: bool = False,
    leaves_only: bool = True,
    include_containers: bool = False,
    include_values: bool = False,
    sort_keys: bool = False,
    max_depth: Optional[int] = None,
) -> Iterator[Union[str, Tuple[str, Any]]]:
    """
    Depth-first traversal that yields all JSONPath-like paths in `obj`.
    By default, yields leaf paths only; see flags to tweak behavior.

    Args:
    obj: Any Python object; dicts and lists are traversed. Tuples are treated as leaves
    (to mirror the setter that only understands lists).
    include_root: If True, include '$' (or '' if combine paths without root) as a node
    when include_containers=True and/or when obj is a leaf.
    leaves_only: If True, only yield paths to non-dict/non-list values.
    include_containers: If True, also yield paths to dict/list containers (including empty ones).
    include_values: If True, yield (path, value) tuples; otherwise just the path strings.
    sort_keys: If True, iterate dict keys in sorted(str(key)) order (deterministic).
    max_depth: Optional positive int to cap recursion depth (root has depth=0). None = unlimited.

    Yields:
    Either the path string, or (path, value) if include_values=True.
    """
    # Prepare root path
    root_path = "$" if include_root else ""

    seen_ids = set()

    def yield_item(path: str, value: Any):
        if include_values:
            return (path, value)
        return path

    def rec(current: Any, path: str, depth: int):
        # Depth cap
        if max_depth is not None and depth > max_depth:
            return

        # Cycle protection for containers
        if isinstance(current, (dict, list)):
            oid = id(current)
            if oid in seen_ids:
                return
            seen_ids.add(oid)

        # Dict
        if isinstance(current, dict):
            if include_containers and not leaves_only:
                yield yield_item(path or ("$" if include_root else ""), current)
            if not current and include_containers and leaves_only:
                # Empty dict counts as a leaf-like container if user wants containers included.
                yield yield_item(path or ("$" if include_root else ""), current)
                return

            # Prepare iteration
            items = current.items()
            if sort_keys:
                # sort by stringified key for deterministic ordering
                items = sorted(items, key=lambda kv: str(kv[0]))

            for k, v in items:
                # JSON keys are strings; if not, coerce and quote with brackets
                if not isinstance(k, str):
                    k_str = str(k)
                else:
                    k_str = k

                child_path = _join_path(path or ("$" if include_root else ""), k_str)
                # Recurse
                if isinstance(v, (dict, list)):
                    # container
                    if include_containers and not leaves_only:
                        yield yield_item(child_path, v)
                    yield from rec(v, child_path, depth + 1)
                else:
                    # leaf
                    if not leaves_only and include_containers:
                        # also include the parent container (already handled), leaf comes too
                        pass
                    yield yield_item(child_path, v)

        # List
        elif isinstance(current, list):
            if include_containers and not leaves_only:
                yield yield_item(path or ("$" if include_root else ""), current)
            if not current and include_containers and leaves_only:
                # Empty list as container-leaf
                yield yield_item(path or ("$" if include_root else ""), current)
                return

            for idx, v in enumerate(current):
                child_path = _join_path(path or ("$" if include_root else ""), idx)
                if isinstance(v, (dict, list)):
                    if include_containers and not leaves_only:
                        yield yield_item(child_path, v)
                    yield from rec(v, child_path, depth + 1)
                else:
                    yield yield_item(child_path, v)

        else:
            # Scalar leaf or unsupported container type (tuple/set/etc. treated as leaf)
            if path or include_root:
                yield yield_item(path or "$", current)
            else:
                # Edge case: scalar root without '$'
                yield yield_item("", current)

    # Optionally include the root itself
    if include_root and include_containers and not leaves_only:
        yield yield_item("$", obj)

    yield from rec(obj, root_path, depth=0)


def list_json_paths(
    obj: Any,
    *,
    include_root: bool = False,
    leaves_only: bool = True,
    include_containers: bool = False,
    sort_keys: bool = False,
    max_depth: Optional[int] = None,
) -> List[str]:
    """
    Convenience wrapper that returns only path strings.
    """
    return list(
        iter_json_paths(
            obj,
            include_root=include_root,
            leaves_only=leaves_only,
            include_containers=include_containers,
            include_values=False,
            sort_keys=sort_keys,
            max_depth=max_depth,
        )
    )


def paths_with_values(
    obj: Any,
    *,
    include_root: bool = False,
    leaves_only: bool = True,
    include_containers: bool = False,
    sort_keys: bool = False,
    max_depth: Optional[int] = None,
    exclude_none: bool = False,
) -> List[Tuple[str, Any]]:
    """
    Return a list of (path, value) pairs for `obj` using the same JSONPath-like syntax.
    Set `exclude_none=True` to drop entries where value is None.
    """
    pairs = iter_json_paths(
        obj,
        include_root=include_root,
        leaves_only=leaves_only,
        include_containers=include_containers,
        include_values=True,
        sort_keys=sort_keys,
        max_depth=max_depth,
    )
    if exclude_none:
        return [(p, v) for p, v in pairs if v is not None]
    return list(pairs)


def path_value_map(
    obj: Any,
    *,
    include_root: bool = False,
    leaves_only: bool = True,
    include_containers: bool = False,
    sort_keys: bool = False,
    max_depth: Optional[int] = None,
    exclude_none: bool = False,
) -> dict[str, Any]:
    """
    Return a dict mapping path -> value.
    """
    pairs = paths_with_values(
        obj,
        include_root=include_root,
        leaves_only=leaves_only,
        include_containers=include_containers,
        sort_keys=sort_keys,
        max_depth=max_depth,
        exclude_none=exclude_none,
    )
    return {p: v for p, v in pairs}
