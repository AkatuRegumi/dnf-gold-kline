"""Pure-data browser collection tests: no external network or browser required."""
import unittest
from collector.browser_collect import snapshot_from_dom


def row(pid, amount, money):
    return {"platform_id": str(pid), "platform_label": str(pid),
            "amount": str(amount), "money": str(money), "displayed": ""}


class BrowserSnapshotContractTest(unittest.TestCase):
    def setUp(self):
        self.region = {"id": "kua2",
                       "source_url": "https://www.yxdr.com/bijiaqi/dnf/youxibi/kua2"}

    def test_multi_platform_dom_excludes_uncertain_7881_category(self):
        rows = [row(17, 4300, 46), row(17, 10000, 112.35),
                row(40, 18145, 196.98), row(40, 2400, 26.1),
                row(40, 10000, 110), row(44, 100000, 1155.76),
                row(44, 150000, 1733.65)]
        result = snapshot_from_dom(
            self.region, {"total": 7, "visible": 7, "rows": rows},
            captured_at="2026-10-28T00:00:00+00:00")
        self.assertEqual(result["quality"], "usable")
        self.assertEqual(result["capture_method"], "rendered_dom")
        self.assertEqual(result["contributing_retail_platforms"], 2)
        self.assertEqual(result["offers_count"], 5)
        self.assertEqual(result["rendered_observation"]["ambiguous_category_rows"], 2)
        self.assertEqual(result["channel_outcomes"][-1]["coin_no"], "unknown")
        self.assertEqual(result["channel_outcomes"][-1]["accepted"], 0)
        self.assertIsNone(result["wholesale_observation"])
        self.assertAlmostEqual(result["best_ratio"], 93.4783, places=4)

    def test_one_retail_platform_is_partial_despite_visible_7881(self):
        rows = [row(17, 4300, 46), row(17, 10000, 110),
                row(44, 20000, 220), row(44, 30000, 330),
                row(44, 40000, 440)]
        result = snapshot_from_dom(self.region,
                    {"total": 5, "visible": 5, "rows": rows})
        self.assertEqual(result["offers_count"], 2)
        self.assertEqual(result["contributing_retail_platforms"], 1)
        self.assertEqual(result["quality"], "partial")

    def test_no_verified_retail_is_not_fabricated(self):
        with self.assertRaisesRegex(ValueError, "没有可核实库存"):
            snapshot_from_dom(self.region, {"total": 1, "visible": 1,
                                            "rows": [row(44, 20000, 220)]})


if __name__ == "__main__":
    unittest.main()
