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

    def test_history(self):
        sample = {"observed_at": "2026-10-11T00:00:00+00:00", "source": "yxdr"}
        h = append_history({"samples": []}, sample)
        self.assertEqual(h["region"], "kua2")
        with self.assertRaises(ValueError):
            append_history(h, sample)


if __name__ == "__main__":
    unittest.main()
