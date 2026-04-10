import importlib.util
import pathlib
import tempfile
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
        workspace = (
            pathlib.Path(tempfile.gettempdir()) / "missing-lint-targets-workspace"
        )
        if workspace.exists():
            self.fail(f"temporary test path unexpectedly exists: {workspace}")

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
