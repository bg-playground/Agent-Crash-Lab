from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from m2_evidence import EvidenceContractError, assert_secret_free_text, validate_evidence

HERE = Path(__file__).resolve().parent
ARTIFACT = HERE / "evidence" / "m1c_characterization.json"


class M2EvidenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    def test_canonical_artifact_validates(self) -> None:
        validate_evidence(self.data)

    def test_canonical_aggregate_is_frozen(self) -> None:
        experiment = self.data["experiment"]
        self.assertEqual(experiment["valid_trials"], 20)
        self.assertEqual(experiment["invalid_infrastructure_attempts"], 0)
        self.assertEqual(experiment["recoveries"], 18)
        self.assertEqual(experiment["failures"], 2)
        self.assertEqual(experiment["recovery_rate"], 0.9)
        self.assertEqual(experiment["failure_rate"], 0.1)
        self.assertEqual(experiment["failure_classes"], {"incomplete_at_shipping": 2})
        self.assertEqual(experiment["failure_probability_wilson_95"], [0.028, 0.301])

    def test_all_20_ordinals_are_represented(self) -> None:
        self.assertEqual([trial["ordinal"] for trial in self.data["trials"]], list(range(1, 21)))

    def test_missing_historical_fields_are_explicit_not_guessed(self) -> None:
        for trial in self.data["trials"][:19]:
            self.assertEqual(trial["objective_outcome"], "unavailable")
            self.assertEqual(trial["failure_class"], "unavailable")
            self.assertIsNone(trial["run_fingerprint"])
            self.assertIsNone(trial["final_state"])
            self.assertIsNone(trial["events"])
            self.assertEqual(trial["replay_available"], "unavailable")
            self.assertEqual(trial["agent_browser_error_status"], "unavailable")
            self.assertEqual(trial["retention_status"], "not_retained")

    def test_retained_trial_20_matches_observed_evidence(self) -> None:
        trial = self.data["trials"][19]
        self.assertEqual(trial["objective_outcome"], "PASS")
        self.assertEqual(trial["failure_class"], "passed")
        self.assertEqual(trial["final_state"]["stage"], "review")
        self.assertFalse(trial["final_state"]["payment_submitted"])
        self.assertEqual(trial["final_state"]["shipping"], "standard")
        self.assertIn("review_rollback", trial["events"])
        self.assertEqual(trial["events"][-1], "review_reached")
        self.assertTrue(trial["replay_available"])

    def test_tampered_aggregate_is_rejected(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["experiment"]["failures"] = 1
        with self.assertRaises(EvidenceContractError):
            validate_evidence(changed)

    def test_wrong_trial_count_is_rejected(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["trials"] = changed["trials"][:-1]
        with self.assertRaises(EvidenceContractError):
            validate_evidence(changed)

    def test_agent_self_report_cannot_be_oracle(self) -> None:
        changed = copy.deepcopy(self.data)
        changed["oracle"]["agent_self_report_is_oracle"] = True
        with self.assertRaises(EvidenceContractError):
            validate_evidence(changed)

    def test_secret_patterns_are_rejected(self) -> None:
        examples = (
            "pt_token=redacted",
            "https://example.preview.getsolari.com/",
            "wss://browser.example.invalid/devtools",
            "signed_replay_url=https://replay.example.invalid/capability",
            "SOLARI_API_KEY=redacted",
            "OPENAI_API_KEY=redacted",
        )
        for example in examples:
            with self.subTest(example=example):
                with self.assertRaises(EvidenceContractError):
                    assert_secret_free_text(example)

    def test_safe_replay_policy_metadata_is_allowed(self) -> None:
        assert_secret_free_text('"signed_replay_urls_committed": false')

    def test_artifact_text_is_secret_free(self) -> None:
        assert_secret_free_text(ARTIFACT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
