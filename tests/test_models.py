from __future__ import annotations

import unittest

from exitpreflight.models import Finding, Severity, meets_threshold


class ModelTests(unittest.TestCase):
    def test_fingerprint_is_stable_and_content_sensitive(self) -> None:
        first = Finding("code", "Title", Severity.HIGH, "Summary", path="a.txt")
        second = Finding("code", "Different title", Severity.HIGH, "Other", path="a.txt")
        changed = Finding("code", "Title", Severity.HIGH, "Summary", path="b.txt")
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertNotEqual(first.fingerprint, changed.fingerprint)
        self.assertEqual(Finding.from_dict(first.to_dict()), first)

    def test_threshold_ordering(self) -> None:
        self.assertTrue(meets_threshold(Severity.CRITICAL, Severity.HIGH))
        self.assertTrue(meets_threshold(Severity.HIGH, Severity.HIGH))
        self.assertFalse(meets_threshold(Severity.MEDIUM, Severity.HIGH))


if __name__ == "__main__":
    unittest.main()
