from __future__ import annotations

import unittest

import m1c_reliability
import reliability_stats


class SharedWilsonModuleTests(unittest.TestCase):
    def test_m1c_reliability_re_exports_the_shared_function(self) -> None:
        self.assertIs(m1c_reliability.wilson_interval, reliability_stats.wilson_interval)
        self.assertEqual(m1c_reliability.WILSON_Z, reliability_stats.WILSON_Z)

    def test_canonical_m1c_interval_is_unchanged(self) -> None:
        # README / evidence: 2 failures in 20 valid trials -> 2.8%-30.1%.
        low, high = reliability_stats.wilson_interval(2, 20)
        self.assertEqual(round(low, 3), 0.028)
        self.assertEqual(round(high, 3), 0.301)


if __name__ == "__main__":
    unittest.main()
