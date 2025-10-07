import inspect
import typing

import pytest

from diff import Delta, diff, patch


def _op_has_field(op_obj, name: str) -> bool:
    return hasattr(op_obj, name)


def _op_get(op_obj, *names) -> typing.Any:
    """Get the first existing attribute among names; raise if none exist."""
    for n in names:
        if hasattr(op_obj, n):
            return getattr(op_obj, n)
    raise AssertionError(f"Operation object has none of the attributes {names}")


def _mk_expected_operation(**kwargs):
    """
    Construct an Operation but only pass fields that are actually supported by its signature.
    Useful if Operation signature has slightly different names in different versions.
    """
    params = inspect.signature(Delta).parameters
    allowed = {k: v for k, v in kwargs.items() if k in params}
    return Delta(**allowed)


# --- Your original tests (kept) -------------------------------------------


@pytest.mark.parametrize(
    ("old", "new", "expected_delta"),
    [
        (
            {"name": "Amin"},
            {"name": "Amin2"},
            [
                Delta(
                    operation="modified",
                    path="$.name",
                    old_value="Amin",
                    new_value="Amin2",
                )
            ],
        )
    ],
)
def test_diff(old: dict, new: dict, expected_delta: list[Delta]):
    result = diff(new=new, old=old)
    assert expected_delta == result


def test_patch_complex():
    old = {"name": "amin"}
    new = {
        "full_name": "a",
        "details": {
            "matrix": [[[1, 2, 3]], [1, 2, 3]],
            "list_object": [{"name": "amin", "matrix": [[1, 2], [1, 4]]}],
        },
    }
    deltas = diff(new=new, old=old)
    patch_result = patch(base=old, deltas=deltas)
    assert patch_result == new


# --- New tests -------------------------------------------------------------


def test_diff_no_changes_is_empty():
    base = {"user": {"name": "Amin", "age": 30}, "tags": ["a", "b"]}
    result = diff(new=base, old=base)
    assert result == []


def test_added_key_expected_op_and_patch_roundtrip():
    old: dict[str, typing.Any] = {}
    new = {"age": 30}
    ops = diff(new=new, old=old)

    # At least one 'added' operation to $.age (value semantics may differ: new_value vs value)
    assert any(
        o.operation == "added"
        and o.path == "$.age"
        and _op_get(o, "new_value", "value") == 30
        for o in ops
    )

    # Roundtrip
    assert patch(base=old, deltas=ops) == new


def test_deleted_key_expected_op_and_patch_roundtrip():
    old = {"name": "Amin"}
    new: dict[str, typing.Any] = {}
    ops = diff(new=new, old=old)

    # At least one 'deleted' operation from $.name (old_value/value semantics)
    assert any(
        o.operation == "deleted"
        and o.path == "$.name"
        and _op_get(o, "old_value", "value") == "Amin"
        for o in ops
    )

    # Roundtrip
    assert patch(base=old, deltas=ops) == new


@pytest.mark.parametrize(
    ("old", "new"),
    [
        # Modify primitive and add nested dict
        ({"a": 1}, {"a": 2, "b": {"c": "x"}}),
        # Modify list items and length
        ({"list": [1, 2, 3]}, {"list": [1, 4, 3, 5]}),
        # Nested lists and dicts
        (
            {"details": {"matrix": [[1, 2], [3, 4]], "meta": {"active": True}}},
            {"details": {"matrix": [[1, 2], [3, 5], [8]], "meta": {"active": False}}},
        ),
        # List of dicts
        (
            {"items": [{"id": 1, "v": "a"}, {"id": 2}]},
            {"items": [{"id": 1, "v": "b"}, {"id": 2, "x": 1}, {"id": 3}]},
        ),
        # None to value, value to None
        (
            {"n": None, "z": 1},
            {"n": 0, "z": None},
        ),
    ],
)
def test_roundtrip_both_directions(old, new):
    # Convert old -> new
    ops_forward = diff(new=new, old=old)
    result_forward = patch(base=old, deltas=ops_forward)
    assert result_forward == new

    # Convert new -> old
    ops_backward = diff(new=old, old=new)
    result_backward = patch(base=new, deltas=ops_backward)
    assert result_backward == old


def test_none_handling_as_value_vs_absence():
    # None treated as a value: modification
    old = {"x": None}
    new = {"x": 1}
    ops = diff(new=new, old=old)
    # Should be a modified (or possibly added if implementation replaces container),
    # but at least path is present and patch succeeds.
    assert any(o.path == "$.x" for o in ops)
    assert patch(base=old, deltas=ops) == new

    # Removing a key entirely should be a 'deleted'
    old2 = {"y": None}
    new2: dict[str, typing.Any] = {}
    ops2 = diff(new=new2, old=old2)
    assert any(o.operation == "deleted" and o.path == "$.y" for o in ops2)
    assert patch(base=old2, deltas=ops2) == new2


def test_multiple_changes_in_one_structure():
    old = {
        "user": {"name": "Amin", "age": 30},
        "tags": ["a", "b", "c"],
        "settings": {"theme": "light"},
    }
    new = {
        "user": {"name": "Amin2", "age": 31, "role": "dev"},
        "tags": ["a", "c", "d"],  # b->deleted, d->added, index change
        "settings": {"theme": "dark"},
    }

    ops = diff(new=new, old=old)

    # Expect at least these paths to show up with the right op kinds
    expect_paths = {
        "$.user.name": "modified",
        "$.user.age": "modified",
        "$.user.role": "added",
        "$.settings.theme": "modified",
    }
    seen = {o.path: o.operation for o in ops if o.path in expect_paths}
    for p, expected_op in expect_paths.items():
        assert seen.get(p) == expected_op, (
            f"Expected {expected_op} at {p}, got {seen.get(p)}"
        )

    # Roundtrip must work
    assert patch(base=old, deltas=ops) == new


def test_diff_then_patch_is_pure_function_of_inputs():
    """
    Ensure calling diff multiple times returns consistent operations
    for the same inputs, and patch result is consistent.
    """
    old = {"x": [1, 2, {"y": "z"}]}
    new = {"x": [1, 3, {"y": "Z"}], "n": 1}

    ops1 = diff(new=new, old=old)
    ops2 = diff(new=new, old=old)
    # Equality of ops may depend on internal ordering; at least lengths match and patch result is same
    assert len(ops1) == len(ops2)
    assert patch(base=old, deltas=ops1) == new
    assert patch(base=old, deltas=ops2) == new


def test_reverse_diff_converts_back_and_forth():
    """
    Explicitly verify that forward diff patches old->new and reverse diff patches new->old.
    """
    old = {"a": 1, "k": {"x": [1, 2]}}
    new = {"a": 2, "k": {"x": [1, 2, 3]}, "b": {"p": 9}}

    forward = diff(new=new, old=old)  # old -> new
    backward = diff(new=old, old=new)  # new -> old

    assert patch(base=old, deltas=forward) == new
    assert patch(base=new, deltas=backward) == old
