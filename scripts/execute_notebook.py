"""execute_notebook.py — run a notebook in place, optionally stopping before a given cell.

Notebook outputs are the committed learning trail, so regenerating them means actually
executing the notebook rather than hand-editing it.

The stop_before argument exists for 03_tiny_gpt_chat.ipynb, whose last code cell is an
interactive `while True: input()` REPL — a plain `nbconvert --execute` hangs on it forever.
That cell carries zero outputs in the committed trail, so skipping it preserves the
committed state exactly rather than papering over it.

    uv run python scripts/execute_notebook.py notebooks/02_tiny_gpt_tuned.ipynb
    uv run python scripts/execute_notebook.py notebooks/03_tiny_gpt_chat.ipynb 7
"""
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

TIMEOUT_SECONDS = 7200          # a full Track A training cell runs ~20-40 min


def main():
    if not 2 <= len(sys.argv) <= 3:
        sys.exit(__doc__)
    path = Path(sys.argv[1]).resolve()
    stop_before = int(sys.argv[2]) if len(sys.argv) == 3 else None

    nb = nbformat.read(path, as_version=4)
    all_cells = nb.cells
    if stop_before is not None:
        tail = all_cells[stop_before:]
        nb.cells = all_cells[:stop_before]
        print(f"executing cells 0..{stop_before - 1} of {path.name}; "
              f"leaving {len(tail)} cell(s) untouched")
    else:
        tail = []
        print(f"executing all {len(all_cells)} cells of {path.name}")

    NotebookClient(
        nb,
        timeout=TIMEOUT_SECONDS,
        kernel_name="python3",
        # run with the notebook's own directory as cwd, so `import tiny_gpt` and the
        # relative "checkpoints/tiny_gpt_v2" path resolve exactly as they do interactively
        resources={"metadata": {"path": str(path.parent)}},
    ).execute()

    nb.cells = list(nb.cells) + tail
    nbformat.write(nb, path)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
