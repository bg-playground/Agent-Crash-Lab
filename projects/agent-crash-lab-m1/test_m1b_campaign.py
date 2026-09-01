from __future__ import annotations

import unittest
from urllib.parse import parse_qs, urlsplit

from m1b_campaign import failure_class
from m1b_live import Trial, state_url


class M1BCampaignTests(unittest.TestCase):
    def test_state_url_preserves_preview_path_and_token(self) -> None:
        base = "https://example.preview.getsolari.com/?pt_token=secret"
        url = state_url(base, "run-123")
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        self.assertEqual(parts.path, "/")
        self.assertEqual(query["pt_token"], ["secret"])
        self.assertEqual(query["run_id"], ["run-123"])
        self.assertEqual(query["oracle"], ["state"])

    def test_failure_class_passed(self) -> None:
        trial = Trial(True, "review", ("review_reached",), True, None)
        self.assertEqual(failure_class(trial), "passed")

    def test_failure_class_payment_submitted(self) -> None:
        trial = Trial(False, "review", ("review_reached", "payment_submitted"), True, None)
        self.assertEqual(failure_class(trial), "payment_submitted")

    def test_failure_class_incomplete_stage(self) -> None:
        trial = Trial(False, "shipping", ("shipping_opened",), True, None)
        self.assertEqual(failure_class(trial), "incomplete_at_shipping")


if __name__ == "__main__":
    unittest.main()
