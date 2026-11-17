"""Badge text parsing (OCR itself is not exercised here)."""
import unittest

from vision import parse_total


class TestParseTotal(unittest.TestCase):
    def test_plain_totals(self):
        self.assertEqual(parse_total("18"), 18)
        self.assertEqual(parse_total("8"), 8)
        self.assertEqual(parse_total("21"), 21)

    def test_soft_totals_use_the_high_value(self):
        self.assertEqual(parse_total("5/15"), 15)    # with slash
        self.assertEqual(parse_total("10/20"), 20)   # 2-digit low with slash
        self.assertEqual(parse_total("515"), 15)     # 5/15 slash dropped
        self.assertEqual(parse_total("5115"), 15)    # 5/15 slash read as '1'
        self.assertEqual(parse_total("818"), 18)     # 8/18
        self.assertEqual(parse_total("111"), 11)     # 1/11 (ace upcard)
        self.assertEqual(parse_total("1020"), 20)    # 10/20 slash dropped
        self.assertEqual(parse_total("10120"), 20)   # 10/20 slash read as '1'

    def test_garbage_is_rejected(self):
        for bad in ("", "0", "00", "123456", "abc", "1"):
            self.assertIsNone(parse_total(bad), bad)

    def test_bust_totals_allowed(self):
        self.assertEqual(parse_total("25"), 25)

    def test_blackjack_badge_parsed_as_bj(self):
        self.assertEqual(parse_total("BJ"), "BJ")
        self.assertEqual(parse_total("bj"), "BJ")
        self.assertEqual(parse_total("8J"), "BJ")

    def test_b_misread_for_8_is_recovered(self):
        self.assertEqual(parse_total("B"), 8)
        self.assertEqual(parse_total("1B"), 18)


if __name__ == "__main__":
    unittest.main()
