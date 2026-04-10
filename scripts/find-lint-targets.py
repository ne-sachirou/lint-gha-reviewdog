#!/usr/bin/env python3

import pathlib
import sys

TARGET_PATTERNS = (
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    ".github/actions/**/action.yml",
    ".github/actions/**/action.yaml",
)


def validate_workspace(workspace: pathlib.Path) -> None:
    if not workspace.exists():
        raise FileNotFoundError(f"workspace does not exist: {workspace}")
    if not workspace.is_dir():
        raise NotADirectoryError(f"workspace is not a directory: {workspace}")


def collect_targets(workspace: pathlib.Path) -> list[pathlib.Path]:
    validate_workspace(workspace)
    targets: set[pathlib.Path] = set()
    for pattern in TARGET_PATTERNS:
        for path in workspace.glob(pattern):
            if path.is_file():
                targets.add(path)
    return sorted(targets)


def main() -> int:
    workspace = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path.cwd()
    try:
        print("true" if collect_targets(workspace) else "false")
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
