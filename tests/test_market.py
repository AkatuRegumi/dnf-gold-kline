import unittest
from collector.market import script_url, assignment, listing, clean_listings, depth, summarize, append_history


class MarketTest(unittest.TestCase):
    def test_script_url(self):
        self.assertEqual(script_url('<script src="/js/CoinSale_yxb_abcd.js"></script>'),
                         'https://www.yxdr.com/js/CoinSale_yxb_abcd.js')
        with self.assertRaises(ValueError):
            script_url('<script src="https://evil.test/CoinSale_yxb_abcd.js"></script>')

    def test_assignment(self):
        source = 'window.bijiaqiChanels=[{"data":"x\\\"y"}];'
        self.assertEqual(assignment(source, 'bijiaqiChanels')[0]['data'], 'x"y')
        self.assertEqual(assignment('window.bijiaqiResult = {"GId":1838};',
                                    'bijiaqiResult'), {"GId":1838})

    def test_listing(self):
        row = listing({"Price": .0115, "Amount": 10000, "Money": 115, "BuyUrl": "a"}, "DD373")
        self.assertAlmostEqual(row["ratio"], 86.956522)
        self.assertIsNone(listing({"Price": .0115, "Amount": -1, "Money": 100}, "X"))
        self.assertIsNone(listing({"Price": 0, "Amount": 10000, "Money": 115}, "X"))

    def test_depth_and_dedup(self):
        rows = [
            {"id": "a", "platform": "A", "ratio": 100, "available_wan": 20000, "lot_cny": 200},
            {"id": "a", "platform": "A", "ratio": 100, "available_wan": 20000, "lot_cny": 200},
            {"id": "b", "platform": "B", "ratio": 80, "available_wan": 20000, "lot_cny": 250},
        ]
        unique = clean_listings(rows)
        self.assertEqual(len(unique), 2)
        self.assertEqual(depth(unique, 30000)["quoted_cny"], 325)
        self.assertIsNone(depth(unique, 100000))
        self.assertEqual(summarize(rows)["offers_count"], 2)

    def test_all_regions_and_isolation(self):
        import json
        from collector.collect import regions, save_sample
        from tempfile import TemporaryDirectory
        from pathlib import Path
        all_regions = regions()
        ids = [r["id"] for r in all_regions]
        self.assertEqual(ids, [
            "kua1", "kua2", "kua3a", "kua3b", "kua4",
            "kua5", "kua6", "kua7", "kua8"])
        self.assertEqual(len(set(ids)), 9)
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            sample2 = {"observed_at": "2026-10-11T01:00:00+00:00", "region": "kua2"}
            sample5 = {"observed_at": "2026-10-11T01:00:00+00:00", "region": "kua5"}
            save_sample("kua2", sample2, folder)
            save_sample("kua5", sample5, folder)
            self.assertEqual(json.loads((folder / "kua2.json").read_text())["samples"], [sample2])
            self.assertEqual(json.loads((folder / "kua5.json").read_text())["samples"], [sample5])
            with self.assertRaises(ValueError):
                save_sample("kua2", sample5, folder)
            self.assertEqual(len(json.loads((folder / "kua2.json").read_text())["samples"]), 1)

    def test_single_region_failure_does_not_abort_other_regions(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from unittest.mock import patch
        from collector.collect import run
        fake = [
            {"id": "kua1", "source_url": "https://www.yxdr.com/bijiaqi/dnf/youxibi/kua1"},
            {"id": "kua2", "source_url": "https://www.yxdr.com/bijiaqi/dnf/youxibi/kua2"}
        ]
        def stub(region):
            if region["id"] == "kua1":
                raise RuntimeError("down")
            return {"region": "kua2", "observed_at": "2026-10-11T01:00:00+00:00"}
        with TemporaryDirectory() as temp, patch("collector.collect.collect", side_effect=stub), patch("collector.collect.time.sleep"):
            passed, failed = run(fake, Path(temp))
            self.assertEqual((passed, failed), (1, 1))
            self.assertFalse((Path(temp) / "kua1.json").exists())
            self.assertTrue((Path(temp) / "kua2.json").exists())

    def test_history(self):
        sample = {"observed_at": "2026-10-11T00:00:00+00:00", "source": "yxdr"}
        h = append_history({"samples": []}, sample)
        self.assertEqual(h["region"], "kua2")
        with self.assertRaises(ValueError):
            append_history(h, sample)


if __name__ == "__main__":
    unittest.main()
