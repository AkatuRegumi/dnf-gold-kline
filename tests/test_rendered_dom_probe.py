"""Offline DOM markup/number parsing tests. Never contact YXDR."""
import unittest

from tools.probe_yxdr_dom import parse_rows


class RenderedDOMTest(unittest.TestCase):
    def test_real_firefox_markup_values_keep_provider_id_and_price(self):
        rows = [
            {"displayed": "0.01069 /93.48", "amount": "4300", "money": "46",
             "platform_id": "17", "platform_label": "UU898"},
            {"displayed": "0.01085 /92.12", "amount": "18145", "money": "196.98",
             "platform_id": "40", "platform_label": "DD373"},
            {"displayed": "0.01087 /91.95", "amount": "2400", "money": "26.1",
             "platform_id": "40", "platform_label": "DD373"},
            {"displayed": "0.01091 /91.60", "amount": "20000", "money": "218.34",
             "platform_id": "44", "platform_label": "7881"},
            {"displayed": "0.01100 /90.91", "amount": "10000", "money": "110",
             "platform_id": "40", "platform_label": "DD373"},
        ]
        result = parse_rows({"total": 5, "visible": 5, "rows": rows})
        self.assertEqual(result["accepted_rows"], 5)
        self.assertEqual(result["platform_count"], 3)
        self.assertEqual(result["platforms"], {"17": 1, "40": 3, "44": 1})
        self.assertAlmostEqual(result["top"][0]["ratio"], 93.4783)
        self.assertAlmostEqual(result["top"][-1]["ratio"], 90.9091)

    def test_does_not_count_missing_or_mismatched_values(self):
        raw = [
            {"displayed": "loading...", "amount": "", "money": "46", "platform_id": "17"},
            {"displayed": "0.0100 /100.00", "amount": "100", "money": "100", "platform_id": "40"},
            {"displayed": "0.0100 /100.00", "amount": "4300", "money": "46", "platform_id": "17"},
            {"displayed": "0.01069 /93.48", "amount": "4300", "money": "46", "platform_id": ""},
        ]
        result = parse_rows({"total": 4, "visible": 4, "rows": raw})
        self.assertEqual(result["accepted_rows"], 0)
        self.assertEqual(result["discarded_rows"], 4)

    def test_limit_only_applies_after_market_coverage_count(self):
        rows = [
            {"displayed": "", "amount": "10000", "money": "110", "platform_id": "17"}
            for _ in range(10)
        ] + [
            {"displayed": "", "amount": "20000", "money": "220", "platform_id": "44"}
        ]
        result = parse_rows({"total": 11, "visible": 11, "rows": rows}, limit=10)
        self.assertEqual(len(result["top"]), 10)
        self.assertEqual(result["accepted_rows"], 11)
        self.assertEqual(result["platform_count"], 2)


if __name__ == "__main__":
    unittest.main()
