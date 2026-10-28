#!/usr/bin/env python3

import json
import pathlib
import re
import sys
from typing import Any


def make_severity(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"error", "high"}:
        return "ERROR"
    if normalized in {"info", "informational"}:
        return "INFO"
    return "WARNING"


def build_rdjson(tool_name: str, diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    return {"source": {"name": tool_name}, "diagnostics": diagnostics}


def make_location(path: str, line: int, column: int) -> dict[str, Any]:
    return {
        "path": path,
        "range": {"start": {"line": max(line, 1), "column": max(column, 1)}},
    }


def normalize_path(path: str) -> str:
    if path.startswith("./"):
        return path[2:]
    return path


def load_payload(path: pathlib.Path) -> list[Any]:
    # The input must be exactly the zizmor JSON document (stdout only). Never
    # scan for JSON inside a mixed log: other output can echo file names from
    # the linted tree, which would let them stand in for the real findings.
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("zizmor JSON payload must be a top-level list")
    return payload


def convert_zizmor(path: pathlib.Path) -> dict[str, Any]:
    findings = load_payload(path)
    diagnostics = []
    for finding in findings:
        primary = None
        for location in finding.get("locations", []):
            if location.get("symbolic", {}).get("kind") == "Primary":
                primary = location
                break
        if primary is None and finding.get("locations"):
            primary = finding["locations"][0]
        if primary is None:
            continue

        symbolic = primary.get("symbolic", {})
        concrete = primary.get("concrete", {})
        local_key = symbolic.get("key", {}).get("Local", {})
        path_value = normalize_path(local_key.get("given_path", ""))
        if not path_value:
            continue

        start = concrete.get("location", {}).get("start_point", {})
        line = int(start.get("row", 1)) + 1
        column = int(start.get("column", 0)) + 1
        message = finding.get("desc", "").strip()
        annotation = symbolic.get("annotation")
        if annotation:
            message = f"{message}: {annotation}"

        diagnostics.append(
            {
                "message": message,
                "severity": make_severity(
                    finding.get("determinations", {}).get("severity")
                ),
                "location": make_location(path_value, line, column),
                "code": {
                    "value": finding.get("ident", "zizmor"),
                    "url": finding.get("url", ""),
                },
            }
        )
    return build_rdjson("zizmor", diagnostics)


ACTIONLINT_PREFIX_RE = re.compile(r"^(?P<path>.+?):(?P<line>\d+):(?P<column>\d+):\s+")


def split_actionlint_code(text: str) -> tuple[str, str | None]:
    """Split a trailing " [code]" off an actionlint message.

    The message can quote workflow-controlled text, so this uses plain string
    scans: a regex with a lazy message followed by an optional group backtracks
    quadratically on long whitespace or "[" runs.
    """
    if not text.endswith("]"):
        return text, None
    end = len(text) - 1
    # The code cannot contain "]", so its "[" lies after the previous "]" and
    # leaves at least one character before the final "]".
    start = text.rfind("]", 0, end) + 1
    open_idx = text.find("[", start, end - 1)
    while open_idx != -1:
        if open_idx > 0 and text[open_idx - 1].isspace():
            code_start = open_idx + 1
            return text[:open_idx].rstrip(), text[code_start:end]
        open_idx = text.find("[", open_idx + 1, end - 1)
    return text, None


def convert_actionlint(path: pathlib.Path) -> dict[str, Any]:
    diagnostics = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        match = ACTIONLINT_PREFIX_RE.match(stripped)
        if match is None:
            continue
        text_start = match.end()
        message, code = split_actionlint_code(stripped[text_start:])
        diagnostics.append(
            {
                "message": message,
                "severity": "ERROR",
                "location": make_location(
                    normalize_path(match.group("path")),
                    int(match.group("line")),
                    int(match.group("column")),
                ),
                "code": {
                    "value": code or "actionlint",
                    "url": "",
                },
            }
        )
    return build_rdjson("actionlint", diagnostics)


KEY_VALUE_RE = re.compile(r'(\w+)=(".*?"|\S+)')


def parse_key_values(line: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, value in KEY_VALUE_RE.findall(line):
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
        values[key] = value
    return values


def find_yaml_anchor(path: pathlib.Path, attrs: dict[str, str]) -> tuple[int, int]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return (1, 1)

    step_id = attrs.get("step_id")
    if step_id:
        patterns = (
            re.compile(rf"^\s*-\s+id:\s*{re.escape(step_id)}\s*$"),
            re.compile(rf"^\s*id:\s*{re.escape(step_id)}\s*$"),
        )
        for pattern in patterns:
            for idx, line in enumerate(lines, start=1):
                if pattern.match(line):
                    return (idx, 1)

    job_name = attrs.get("job_name")
    if job_name:
        pattern = re.compile(rf"^\s*{re.escape(job_name)}:\s*$")
        for idx, line in enumerate(lines, start=1):
            if pattern.match(line):
                return (idx, 1)

    step_name = attrs.get("step_name")
    if step_name:
        pattern = re.compile(rf'^\s*name:\s*["\']?{re.escape(step_name)}["\']?\s*$')
        for idx, line in enumerate(lines, start=1):
            if pattern.match(line):
                return (idx, 1)

    return (1, 1)


def convert_ghalint(path: pathlib.Path, workspace: pathlib.Path) -> dict[str, Any]:
    diagnostics = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if "violates policies" not in line:
            continue
        attrs = parse_key_values(line)
        file_path = attrs.get("workflow_file_path") or attrs.get("action_file_path")
        if not file_path:
            continue
        normalized_path = normalize_path(file_path)
        loc_line, loc_column = find_yaml_anchor(workspace / normalized_path, attrs)
        diagnostics.append(
            {
                "message": attrs.get("error", "policy violation"),
                "severity": "WARNING",
                "location": make_location(normalized_path, loc_line, loc_column),
                "code": {
                    "value": attrs.get("policy_name", "ghalint"),
                    "url": attrs.get("reference", ""),
                },
            }
        )
    return build_rdjson("ghalint", diagnostics)


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "usage: convert-to-rdjson.py <actionlint|zizmor|ghalint> <input> [workspace]",
            file=sys.stderr,
        )
        return 2

    tool = sys.argv[1]
    input_path = pathlib.Path(sys.argv[2])
    if tool == "actionlint":
        payload = convert_actionlint(input_path)
    elif tool == "zizmor":
        payload = convert_zizmor(input_path)
    elif tool == "ghalint":
        if len(sys.argv) < 4:
            print("workspace path is required for ghalint", file=sys.stderr)
            return 2
        payload = convert_ghalint(input_path, pathlib.Path(sys.argv[3]))
    else:
        print(f"unsupported tool: {tool}", file=sys.stderr)
        return 2

    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
