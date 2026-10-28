import importlib.util
import pathlib
import tempfile
import time
import unittest

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "scripts" / "convert-to-rdjson.py"
)
TARGET_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "scripts" / "find-lint-targets.py"
)
SPEC = importlib.util.spec_from_file_location("convert_to_rdjson", MODULE_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
TARGET_SPEC = importlib.util.spec_from_file_location(
    "find_lint_targets", TARGET_MODULE_PATH
)
assert TARGET_SPEC is not None
TARGET_MODULE = importlib.util.module_from_spec(TARGET_SPEC)
assert TARGET_SPEC.loader is not None
TARGET_SPEC.loader.exec_module(TARGET_MODULE)


class LoadPayloadTest(unittest.TestCase):
    def test_skips_ansi_prefix_before_json_payload(self) -> None:
        content = '\x1b[2mnote\x1b[0m\n[{"ident":"demo","locations":[]}]'

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write(content)
            path = pathlib.Path(handle.name)

        try:
            self.assertEqual(
                MODULE.load_payload(path), [{"ident": "demo", "locations": []}]
            )
        finally:
            path.unlink()

    def test_raises_when_json_payload_is_missing(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("plain text only")
            path = pathlib.Path(handle.name)

        try:
            with self.assertRaises(ValueError):
                MODULE.load_payload(path)
        finally:
            path.unlink()


class ConvertZizmorTest(unittest.TestCase):
    def test_converts_sample_finding_to_rdjson(self) -> None:
        fixture = (
            pathlib.Path(__file__).resolve().parent
            / "fixtures"
            / "zizmor-log-with-finding.txt"
        )

        payload = MODULE.convert_zizmor(fixture)

        self.assertEqual(payload["source"]["name"], "zizmor")
        self.assertEqual(len(payload["diagnostics"]), 1)
        diagnostic = payload["diagnostics"][0]
        self.assertEqual(
            diagnostic["message"],
            "secrets referenced without a dedicated environment: secret is accessed outside of a dedicated environment",
        )
        self.assertEqual(diagnostic["severity"], "WARNING")
        self.assertEqual(
            diagnostic["location"],
            {
                "path": ".github/workflows/wf-observe-gha.yaml",
                "range": {"start": {"line": 34, "column": 55}},
            },
        )
        self.assertEqual(
            diagnostic["code"],
            {
                "value": "secrets-outside-env",
                "url": "https://docs.zizmor.sh/audits/#secrets-outside-env",
            },
        )


class ConvertActionlintTest(unittest.TestCase):
    def test_converts_sample_finding_to_rdjson(self) -> None:
        fixture = (
            pathlib.Path(__file__).resolve().parent
            / "fixtures"
            / "actionlint-log-with-finding.txt"
        )

        payload = MODULE.convert_actionlint(fixture)

        self.assertEqual(payload["source"]["name"], "actionlint")
        self.assertEqual(len(payload["diagnostics"]), 1)
        diagnostic = payload["diagnostics"][0]
        self.assertEqual(
            diagnostic["message"],
            'job "dummy" needs job "no-such-job" which does not exist in this workflow',
        )
        self.assertEqual(diagnostic["severity"], "ERROR")
        self.assertEqual(
            diagnostic["location"],
            {
                "path": ".github/workflows/dummy-fail-linters.yaml",
                "range": {"start": {"line": 12, "column": 3}},
            },
        )
        self.assertEqual(
            diagnostic["code"],
            {
                "value": "job-needs",
                "url": "",
            },
        )


class ConvertActionlintLineTest(unittest.TestCase):
    def convert_line(self, line: str) -> list[dict]:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write(line + "\n")
            path = pathlib.Path(handle.name)

        try:
            return MODULE.convert_actionlint(path)["diagnostics"]
        finally:
            path.unlink()

    def test_message_without_code_uses_default_code(self) -> None:
        diagnostics = self.convert_line("./ci.yaml:3:4: something is wrong")

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]["message"], "something is wrong")
        self.assertEqual(
            diagnostics[0]["location"],
            {"path": "ci.yaml", "range": {"start": {"line": 3, "column": 4}}},
        )
        self.assertEqual(diagnostics[0]["code"]["value"], "actionlint")

    def test_splits_only_the_trailing_code(self) -> None:
        diagnostics = self.convert_line("ci.yaml:3:4: bad [x] key [y] [syntax-check]")

        self.assertEqual(diagnostics[0]["message"], "bad [x] key [y]")
        self.assertEqual(diagnostics[0]["code"]["value"], "syntax-check")

    def test_bracket_without_leading_whitespace_is_part_of_message(self) -> None:
        diagnostics = self.convert_line("ci.yaml:3:4: key[0] is bad")
        self.assertEqual(diagnostics[0]["message"], "key[0] is bad")
        self.assertEqual(diagnostics[0]["code"]["value"], "actionlint")

        diagnostics = self.convert_line("ci.yaml:3:4: key[syntax-check]")
        self.assertEqual(diagnostics[0]["message"], "key[syntax-check]")
        self.assertEqual(diagnostics[0]["code"]["value"], "actionlint")

    def test_long_whitespace_and_bracket_runs_are_linear(self) -> None:
        size = 200_000
        lines = (
            'ci.yaml:1:2: unexpected key "a' + " " * size + 'b" for step',
            "ci.yaml:1:2: message" + " " * size + "[",
            "ci.yaml:1:2: message" + " [" * size + "]",
            "ci.yaml:1:2: message" + " [a" * size,
        )

        for line in lines:
            started = time.monotonic()
            diagnostics = self.convert_line(line)
            elapsed = time.monotonic() - started

            self.assertEqual(len(diagnostics), 1)
            self.assertLess(elapsed, 5.0)


class CollectTargetsTest(unittest.TestCase):
    def test_detects_workflow_and_action_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = pathlib.Path(tmp_dir)
            workflow = workspace / ".github" / "workflows" / "ci.yaml"
            action = workspace / ".github" / "actions" / "lint" / "action.yml"
            workflow.parent.mkdir(parents=True)
            action.parent.mkdir(parents=True)
            workflow.write_text("name: ci\n", encoding="utf-8")
            action.write_text(
                "name: lint\nruns:\n  using: composite\n  steps: []\n", encoding="utf-8"
            )

            self.assertEqual(
                TARGET_MODULE.collect_targets(workspace),
                [action, workflow],
            )

    def test_ignores_workspace_without_github_actions_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = pathlib.Path(tmp_dir)
            (workspace / "README.md").write_text("hello\n", encoding="utf-8")

            self.assertEqual(TARGET_MODULE.collect_targets(workspace), [])

    def test_raises_when_workspace_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = pathlib.Path(tmp_dir) / "missing-lint-targets-workspace"

        self.assertFalse(workspace.exists())
        with self.assertRaises(FileNotFoundError):
            TARGET_MODULE.collect_targets(workspace)

    def test_raises_when_workspace_is_not_a_directory(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("hello\n")
            workspace = pathlib.Path(handle.name)

        try:
            with self.assertRaises(NotADirectoryError):
                TARGET_MODULE.collect_targets(workspace)
        finally:
            workspace.unlink()


if __name__ == "__main__":
    unittest.main()
