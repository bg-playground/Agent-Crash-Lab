from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from m1b_live import Trial
from m1c_reliability import (
    CONDITION,
    PREVIEW_RENEWAL_SECONDS,
    VALID_TRIALS,
    collect_valid_trials,
    summarize,
    wilson_interval,
)


def trial(passed: bool, stage: str = "review", events: tuple[str, ...] = ()) -> Trial:
    return Trial(
        passed=passed,
        stage=stage,
        events=events,
        replay_available=True,
        error=None,
    )


class WilsonIntervalTests(unittest.TestCase):
    def test_rejects_invalid_counts(self) -> None:
        with self.assertRaises(ValueError):
            wilson_interval(0, 0)
        with self.assertRaises(ValueError):
            wilson_interval(-1, 20)
        with self.assertRaises(ValueError):
            wilson_interval(21, 20)

    def test_zero_of_twenty_has_nonzero_upper_bound(self) -> None:
        low, high = wilson_interval(0, 20)
        self.assertEqual(low, 0.0)
        self.assertAlmostEqual(high, 0.161125, places=5)

    def test_ten_of_twenty_is_symmetric_around_half(self) -> None:
        low, high = wilson_interval(10, 20)
        self.assertAlmostEqual(low, 0.299298, places=5)
        self.assertAlmostEqual(high, 0.700702, places=5)

    def test_twenty_of_twenty_has_nonzero_lower_bound(self) -> None:
        low, high = wilson_interval(20, 20)
        self.assertAlmostEqual(low, 0.838875, places=5)
        self.assertEqual(high, 1.0)


class SummaryTests(unittest.TestCase):
    def test_requires_exactly_twenty_valid_trials(self) -> None:
        with self.assertRaises(ValueError):
            summarize([trial(True)] * (VALID_TRIALS - 1), 0)

    def test_aggregates_passes_failures_and_classes(self) -> None:
        trials = [trial(True) for _ in range(15)]
        trials += [trial(False, "shipping") for _ in range(4)]
        trials += [trial(False, "review", ("payment_submitted",))]

        result = summarize(trials, invalid_attempts=2)

        self.assertEqual(result.valid_trials, 20)
        self.assertEqual(result.invalid_attempts, 2)
        self.assertEqual(result.passes, 15)
        self.assertEqual(result.failures, 5)
        self.assertEqual(result.recovery_rate, 0.75)
        self.assertEqual(result.failure_rate, 0.25)
        self.assertEqual(
            result.failure_classes,
            {"incomplete_at_shipping": 4, "payment_submitted": 1},
        )


class PreviewRenewalTests(unittest.IsolatedAsyncioTestCase):
    async def test_time_based_renewal_preserves_condition_and_twenty_valid_trials(self) -> None:
        clock_values = iter([0.0] + [PREVIEW_RENEWAL_SECONDS + i for i in range(100)])
        clock = lambda: next(clock_values)
        renew = AsyncMock(return_value="https://renewed.invalid/?pt_token=redacted")
        execute = AsyncMock(return_value=trial(True))

        with patch("m1c_reliability.execute_trial", execute):
            valid, invalid = await collect_valid_trials(
                object(),
                "https://initial.invalid/?pt_token=redacted",
                renew,
                monotonic=clock,
            )

        self.assertEqual(len(valid), VALID_TRIALS)
        self.assertEqual(invalid, 0)
        self.assertGreaterEqual(renew.await_count, 1)
        self.assertEqual(execute.await_count, VALID_TRIALS)
        for call in execute.await_args_list:
            self.assertEqual(call.args[2], CONDITION)

    async def test_invalid_attempt_is_replaced_after_preview_renewal(self) -> None:
        from m1b_campaign import CampaignInfrastructureError

        outcomes = [CampaignInfrastructureError("transport failed")] + [trial(True)] * VALID_TRIALS
        execute = AsyncMock(side_effect=outcomes)
        renew = AsyncMock(return_value="https://renewed.invalid/?pt_token=redacted")
        clock = lambda: 0.0

        with patch("m1c_reliability.execute_trial", execute):
            valid, invalid = await collect_valid_trials(
                object(),
                "https://initial.invalid/?pt_token=redacted",
                renew,
                monotonic=clock,
            )

        self.assertEqual(len(valid), VALID_TRIALS)
        self.assertEqual(invalid, 1)
        self.assertEqual(execute.await_count, VALID_TRIALS + 1)
        self.assertEqual(renew.await_count, 1)
        for call in execute.await_args_list:
            self.assertEqual(call.args[2], CONDITION)


if __name__ == "__main__":
    unittest.main()
