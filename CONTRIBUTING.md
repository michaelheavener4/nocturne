# Contributing

## Install

Python 3.11 or newer (`requires-python` in `pyproject.toml`). CI runs 3.11, 3.12, and 3.13.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`pip install -e .` installs the runtime package (`pydantic`, `numpy`). The `dev` extra adds `pytest`.

## Demo

```bash
muse demo --prompt "dark and tense, 92 bpm"
```

That runs the offline pipeline (mock DAW) and writes:

- `data/projects/muse_sketch.mid`
- `data/projects/muse_sketch.json`

`data/` is gitignored.

## Gate

With the `dev` extra installed, from the repository root:

```bash
python tools/verify.py
```

That is the merge gate. It runs `pytest` on `tests/`, then a multi-feedback MIDI hash probe. It prints every probe hash and exits 0 only when the suite passes and the hashes are distinct.

`.github/workflows/ci.yml` runs on push and pull request. Each Python version installs with `pip install -e .`, runs pytest when `tests/` is in the tree, and checks that `muse demo --prompt "ci smoke"` writes a MIDI file.
