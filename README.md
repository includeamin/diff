# diff

Diff is a library to calculate deltas between structured data.

## Features

- Calculate detlas
- Rebuild via deltas

## Supported Formats

- [x] JSON
- [ ] YAML
- [ ] XML
- [ ] TOML

## Usage

### Diff

```python
import diff

old = {"name": "David"}
new = {"name": "Alex"}
deltas = diff.diff(new=new, old=old)

for delta in deltas:
    print(delta)

```

Output

```text
Operation(op='modified', path='$.name', new_value='Alex', old_value='David')
```

### Rebuild

```python
import diff

old = {"name": "David"}
new = {"name": "Alex"}
deltas = diff.diff(new=new, old=old)

rebuild_new = diff.patch(base=old, deltas=deltas)

assert rebuild_new == old
```

## Install

```bash
poetry add git+https://github.com/includeamin/diff.git#tag
```