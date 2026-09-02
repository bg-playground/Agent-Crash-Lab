from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from m2_evidence import assert_secret_free_text, validate_evidence_file
from m2_report import DEFAULT_EVIDENCE, generate_report, render_report


class M2ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = validate_evidence_file(DEFAULT_EVIDENCE)

    def test_render_is_deterministic(self) -> None:
        first = render_report(self.data)
        second = render_report(self.data)
        self.assertEqual(first, second)

    def test_report_contains_canonical_headline_values(self) -> None:
        report = render_report(self.data)
        self.assertIn("18/20", report)
        self.assertIn("2/20", report)
        self.assertIn("90.0%", report)
        self.assertIn("10.0%", report)
        self.assertIn("2.8%–30.1%", report)
        self.assertIn("incomplete_at_shipping", report)

    def test_report_explains_oracle_and_scope(self) -> None:
        report = render_report(self.data)
        self.assertIn("server_authoritative_state", report)
        self.assertIn("agent's own final message is explicitly not the oracle", report)
        self.assertIn("do not establish a universal reliability rate", report)
        self.assertIn("not a universal model reliability guarantee", report)

    def test_report_is_transparent_about_missing_trial_history(self) -> None:
        report = render_report(self.data)
        self.assertIn("does not guess which historical ordinals", report)
        self.assertIn("Unavailable — not retained", report)
        self.assertIn("Trial 20", report)

    def test_report_includes_twenty_trial_cells(self) -> None:
        report = render_report(self.data)
        self.assertEqual(report.count('class="trial unknown"'), 19)
        self.assertEqual(report.count('class="trial pass"'), 1)
        self.assertEqual(report.count('class="trial fail"'), 0)

    def test_report_does_not_render_capability_secrets(self) -> None:
        report = render_report(self.data)
        assert_secret_free_text(report)
        self.assertNotIn("wss://", report.lower())
        self.assertNotIn("pt_token", report.lower())
        self.assertNotIn("preview.getsolari.com", report.lower())

    def test_offline_generation_writes_standalone_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.html"
            generated = generate_report(DEFAULT_EVIDENCE, output)
            self.assertEqual(generated, output)
            text = output.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("<!doctype html>"))
            self.assertIn("<style>", text)
            self.assertNotIn("<script", text.lower())
            self.assertNotIn("http://", text.lower())
            self.assertNotIn("https://", text.lower())


if __name__ == "__main__":
    unittest.main()
