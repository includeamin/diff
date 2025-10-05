import copy
import typing
from typing import Any

from diff.diff import Operation

Token = str | int  # str for dict keys, int for list indices


class JsonPathError(ValueError):
    pass


def _tokenize_json_path(path: str) -> list[Token]:
    """
    Tokenize a JSONPath-like string into a list of tokens.
    - Dict keys -> strings
    - List indices -> integers
    Supported syntax:
    $.a.b[2]["key.with.dots"][0]
    Notes:
    - Leading '$' is optional.
    - Dot-notation for simple keys.
    - Brackets for indices and quoted keys. Quotes can be ' or ".
    - Escaping inside quoted keys: backslash escapes the quote and backslash (\", \', \\).
    """
    if not isinstance(path, str) or not path:
        raise JsonPathError("Path must be a non-empty string.")

    i = 0
    n = len(path)
    tokens: list[Token] = []

    # Skip optional leading '$' and optional following '.'
    if i < n and path[i] == "$":
        i += 1
        if i < n and path[i] == ".":
            i += 1

    def read_simple_key(start: int) -> tuple[str, int]:
        j = start
        while j < n and path[j] not in ".[":
            j += 1
        if j == start:
            raise JsonPathError(f"Expected key at position {start} in '{path}'")
        return path[start:j], j

    def read_bracket_key_or_index(start: int) -> tuple[Token, int]:
        # start at '[', return (token, new_index_after_'])
        j = start + 1
        if j >= n:
            raise JsonPathError(f"Unclosed '[' at position {start} in '{path}'")

        if path[j] in ("'", '"'):
            # Quoted key
            quote = path[j]
            j += 1
            buf = []
            while j < n:
                ch = path[j]
                if ch == "\\":  # escape sequence
                    j += 1
                    if j >= n:
                        raise JsonPathError("Trailing backslash in quoted key.")
                    esc = path[j]
                    if esc in [quote, "\\"]:
                        buf.append(esc)
                    else:
                        # Keep unknown escape as-is (e.g., \n), or handle specially if desired
                        buf.append(esc)
                    j += 1
                    continue
                if ch == quote:
                    j += 1
                    break
                buf.append(ch)
                j += 1
            else:
                raise JsonPathError(
                    f"Unclosed quoted key starting at position {start} in '{path}'"
                )

            # Expect closing ']'
            if j >= n or path[j] != "]":
                raise JsonPathError(
                    f"Expected ']' after quoted key at position {j} in '{path}'"
                )
            return "".join(buf), j + 1

        # Numeric index
        k = j
        while k < n and path[k].isdigit():
            k += 1
        if k == j:
            raise JsonPathError(
                f"Expected non-negative integer index after '[' at position {start} in '{path}'"
            )
        if k >= n or path[k] != "]":
            raise JsonPathError(f"Expected ']' after index at position {k} in '{path}'")
        idx = int(path[j:k])
        return idx, k + 1

    while i < n:
        ch = path[i]
        if ch == ".":
            i += 1  # skip redundant dots (e.g., '$.a..b' would error on next step)
            continue
        elif ch == "[":
            token, i = read_bracket_key_or_index(i)
            tokens.append(token)
        else:
            key, i = read_simple_key(i)
            tokens.append(key)

    return tokens


def set_by_json_path(
    doc: Any, path: str, value: Any, *, create_missing: bool = True
) -> Any:
    """
    Set `value` into `doc` following a JSONPath-like `path`, creating
    intermediate dicts/lists if `create_missing` is True.

    Mutates `doc` in place and also returns it for convenience.

    Raises:
    - JsonPathError on path syntax errors.
    - TypeError when the path expects a dict/list but finds another type.
    - IndexError for negative indices (not supported).
    """
    tokens = _tokenize_json_path(path)
    if not tokens:
        raise JsonPathError("Path resolves to the root; set on '$' is not supported.")

    # We'll walk down, creating as needed.
    current = doc
    parents: list[tuple[Any, Token]] = (
        []
    )  # (container, token used to access) if you later want force-replace
    for idx, tok in enumerate(tokens):
        last = idx == len(tokens) - 1
        next_tok = None if last else tokens[idx + 1]

        if isinstance(tok, str):
            # Expect dict
            if not isinstance(current, dict):
                raise TypeError(
                    f"Expected dict at step {idx} for key '{tok}', found {type(current).__name__}"
                )
            if last:
                current[tok] = value
                return doc
            # create if missing
            if tok not in current or current[tok] is None:
                if not create_missing:
                    raise KeyError(
                        f"Missing key '{tok}' at step {idx} and create_missing=False"
                    )
                current[tok] = [] if isinstance(next_tok, int) else {}
            parents.append((current, tok))
            current = current[tok]

        else:
            # list index
            index = tok
            if index < 0:
                raise IndexError(
                    "Negative indices are not supported in this implementation."
                )
            if not isinstance(current, list):
                raise TypeError(
                    f"Expected list at step {idx} for index [{index}], found {type(current).__name__}"
                )
            # extend if needed
            if index >= len(current):
                if not create_missing:
                    raise IndexError(
                        f"Index {index} out of range at step {idx} and create_missing=False"
                    )
                current.extend([None] * (index - len(current) + 1))
            if last:
                current[index] = value
                return doc
            if current[index] is None:
                if not create_missing:
                    raise KeyError(
                        f"Missing element at index {index} (None) and create_missing=False"
                    )
                current[index] = [] if isinstance(next_tok, int) else {}
            parents.append((current, index))
            current = current[index]

    # Should not reach here
    return doc


def get_by_json_path(doc: Any, path: str) -> Any:
    """
    Retrieve a value from `doc` following the same JSONPath-like syntax.
    """
    tokens = _tokenize_json_path(path)
    current = doc
    for idx, tok in enumerate(tokens):
        if isinstance(tok, str):
            if not isinstance(current, dict) or tok not in current:
                raise KeyError(f"Path segment {tok} not found at step {idx}")
            current = current[tok]
        else:
            if not isinstance(current, list):
                raise TypeError(
                    f"Expected list at step {idx} for index [{tok}], found {type(current).__name__}"
                )
            if tok < 0 or tok >= len(current):
                raise IndexError(f"Index {tok} out of range at step {idx}")
            current = current[tok]
    return current


def _delete_in_parent(parent: Any, tok: Token, *, remove_from_list: bool) -> None:
    """
    Remove child referenced by `tok` from `parent`.
    - For dicts: del parent[tok]
    - For lists: if remove_from_list=True -> del parent[tok]; else -> parent[tok] = None
    """
    if isinstance(tok, str):
        if not isinstance(parent, dict):
            raise TypeError(
                f"Expected dict parent to delete key '{tok}', found {type(parent).__name__}"
            )
        if tok in parent:
            del parent[tok]
    else:
        # list index
        if not isinstance(parent, list):
            raise TypeError(
                f"Expected list parent to delete index [{tok}], found {type(parent).__name__}"
            )
        if 0 <= tok < len(parent):
            if remove_from_list:
                del parent[tok]
            else:
                parent[tok] = None


def _is_empty_container(obj: Any) -> bool:
    """Return True if obj is an empty dict or empty list."""
    return (isinstance(obj, dict) and len(obj) == 0) or (
        isinstance(obj, list) and len(obj) == 0
    )


def pop_by_json_path(
    doc: Any,
    path: str,
    *,
    missing_ok: bool = False,
    remove_from_list: bool = False,
    prune_empty: bool = False,
) -> Any:
    """
    Remove and return the value at `path`. Behaves like delete_by_json_path but returns the removed value.
    If the path is missing and missing_ok=True, returns None and leaves `doc` unchanged.
    """
    tokens = _tokenize_json_path(path)
    if not tokens:
        raise JsonPathError("Path resolves to the root; popping '$' is not supported.")

    # Traverse to parent
    current = doc
    parents: list[tuple[Any, Token]] = []
    try:
        for idx, tok in enumerate(tokens[:-1]):
            if isinstance(tok, str):
                if (
                    not isinstance(current, dict)
                    or tok not in current
                    or current[tok] is None
                ):
                    if missing_ok:
                        return None
                    raise KeyError(f"Missing key '{tok}' at step {idx}")  # noqa: TRY301
                parents.append((current, tok))
                current = current[tok]
            else:
                if not isinstance(current, list) or tok < 0 or tok >= len(current):
                    if missing_ok:
                        return None
                    raise IndexError(
                        f"Index {tok} out of range at step {idx}"
                    )  # noqa: TRY301
                if current[tok] is None:
                    if missing_ok:
                        return None
                    raise KeyError(
                        f"None found at index {tok} at step {idx}"
                    )  # noqa: TRY301
                parents.append((current, tok))
                current = current[tok]
    except (TypeError, KeyError, IndexError):
        if missing_ok:
            return None
        raise

    # Pop at leaf
    leaf = tokens[-1]
    removed = None
    try:
        if isinstance(leaf, str):
            if not isinstance(current, dict):
                if missing_ok:
                    return None
                raise TypeError(  # noqa: TRY301
                    f"Expected dict at leaf for key '{leaf}', found {type(current).__name__}"
                )
            if leaf not in current:
                if missing_ok:
                    return None
                raise KeyError(f"Key '{leaf}' not found at leaf")  # noqa: TRY301
            removed = current[leaf]
            del current[leaf]
        else:
            if not isinstance(current, list):
                if missing_ok:
                    return None
                raise TypeError(  # noqa: TRY301
                    f"Expected list at leaf for index [{leaf}], found {type(current).__name__}"
                )
            if leaf < 0 or leaf >= len(current):
                if missing_ok:
                    return None
                raise IndexError(f"Index {leaf} out of range at leaf")  # noqa: TRY301
            if remove_from_list:
                removed = current[leaf]
                del current[leaf]
            else:
                removed = current[leaf]
                current[leaf] = None
    except (TypeError, KeyError, IndexError):
        if missing_ok:
            return None
        raise

    # Prune if requested
    if prune_empty:
        child = current
        for depth in range(len(parents) - 1, -1, -1):
            parent, tok_to_child = parents[depth]
            if _is_empty_container(child):
                _delete_in_parent(
                    parent, tok_to_child, remove_from_list=remove_from_list
                )
                child = parent
            else:
                break

    return removed


def patch(
    base: dict[str, typing.Any], operations: list[Operation]
) -> dict[str, typing.Any]:
    output = copy.deepcopy(base)
    for op in operations:
        if op.op == "deleted":
            pop_by_json_path(output, op.path, prune_empty=True, remove_from_list=True)
            continue
        set_by_json_path(
            output,
            op.path,
            op.new_value,
        )
    return output
