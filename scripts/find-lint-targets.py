#!/usr/bin/env python3

import pathlib
import sys

TARGET_PATTERNS = (
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    ".github/actions/**/action.yml",
    ".github/actions/**/action.yaml",
)


def collect_targets(workspace: pathlib.Path) -> list[pathlib.Path]:
    targets: set[pathlib.Path] = set()
    for pattern in TARGET_PATTERNS:
        for path in workspace.glob(pattern):
            if path.is_file():
                targets.add(path)
    return sorted(targets)


def main() -> int:
    workspace = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path.cwd()
    print("true" if collect_targets(workspace) else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
