import importlib.util
import pathlib
import tempfile
import unittest

MODULE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "scripts" / "convert-to-rdjson.py"
)
SPEC = importlib.util.spec_from_file_location("convert_to_rdjson", MODULE_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


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


if __name__ == "__main__":
    unittest.main()
