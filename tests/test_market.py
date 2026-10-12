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

    def test_staggered_market_groups(self):
        from collector.collect import regions, pick_regions
        from datetime import datetime, timezone
        opts = regions()
        groups = []
        for hour in (0, 4, 8):
            selected = pick_regions(opts, "scheduled", datetime(2026, 10, 11, hour, tzinfo=timezone.utc))
            self.assertEqual(len(selected), 3)
            groups.extend(r["id"] for r in selected)
        self.assertCountEqual(groups, [r["id"] for r in opts])
        next_slot = pick_regions(opts, "scheduled", datetime(2026, 10, 11, 12, tzinfo=timezone.utc))
        self.assertEqual(next_slot, pick_regions(opts, "scheduled", datetime(2026, 10, 11, 0, tzinfo=timezone.utc)))
        self.assertEqual(pick_regions(opts, "all"), opts)
        self.assertEqual([r["id"] for r in pick_regions(opts, "kua8")], ["kua8"])

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
            import json
            health = json.loads((Path(temp) / "collection_status.json").read_text())
            self.assertEqual(health["regions"]["kua1"]["outcome"], "failed")
            self.assertEqual(health["regions"]["kua2"]["outcome"], "success")

    def test_explicit_groups_survive_delayed_start(self):
        from collector.collect import regions, pick_regions
        from datetime import datetime, timezone
        opts = regions()
        expected = [
            ["kua1", "kua3b", "kua6"],
            ["kua2", "kua4", "kua7"],
            ["kua3a", "kua5", "kua8"],
        ]
        late = datetime(2026, 10, 11, 11, 59, tzinfo=timezone.utc)
        for i, ids in enumerate(expected):
            self.assertEqual([r["id"] for r in pick_regions(opts, f"group{i}", late)], ids)

    def test_collection_health_separate_from_quotes(self):
        import json
        from collector.collect import save_attempt, save_sample
        from tempfile import TemporaryDirectory
        from pathlib import Path
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            snap = {"region": "kua6", "observed_at": "2026-10-11T00:00:00+00:00"}
            save_sample("kua6", snap, data_dir)
            save_attempt("kua6", "failed", data_dir, reason="ValueError: script missing")
            self.assertEqual(json.loads((data_dir / "kua6.json").read_text())["samples"], [snap])
            status = json.loads((data_dir / "collection_status.json").read_text())
            self.assertEqual(status["regions"]["kua6"]["outcome"], "failed")
            self.assertIn("script missing", status["regions"]["kua6"]["reason"])
            save_attempt("kua6", "success", data_dir, quality="partial")
            status = json.loads((data_dir / "collection_status.json").read_text())
            self.assertEqual(status["regions"]["kua6"]["quality"], "partial")
            self.assertNotIn("reason", status["regions"]["kua6"])

    def test_safe_channel_diagnostics(self):
        from collector.collect import classify_channel_response
        self.assertEqual(classify_channel_response({"success": 1, "data": []}), "ok")
        self.assertEqual(classify_channel_response({"success": 0, "debug": "Too many requests"}), "rate_limited")
        self.assertEqual(classify_channel_response({"success": 0, "debug": "Captcha required"}), "access_restricted")
        self.assertEqual(classify_channel_response({"success": 0, "debug": "secret=PRIVATE"}), "upstream_rejected")

    def test_attempt_history_does_not_rewrite_market_data(self):
        from collector.collect import save_attempt
        from tempfile import TemporaryDirectory
        from pathlib import Path
        import json
        with TemporaryDirectory() as td:
            folder = Path(td)
            for i in range(44):
                save_attempt("kua7", "success", folder, quality="partial", sample={
                    "offers_count": 4, "successful_channels": 2, "attempted_channels": 4,
                    "channel_outcomes": [{"id": 44, "state": "upstream_rejected"}],
                })
            state = json.loads((folder / "collection_status.json").read_text())
            self.assertEqual(len(state["history"]["kua7"]), 40)
            self.assertEqual(state["regions"]["kua7"]["channel_outcomes"][0]["id"], 44)
            self.assertFalse((folder / "kua7.json").exists())

    def test_cadence_requires_history_and_consistency(self):
        from tools.evaluate_sampling_health import evaluate
        from datetime import datetime, timedelta, timezone
        end = datetime(2026, 10, 11, 15, tzinfo=timezone.utc)
        def records(bad=False):
            return [{
                "attempted_at": (end - timedelta(hours=(11-i)*8)).isoformat(),
                "outcome": "success", "quality": "partial" if (bad and i % 3 == 0) else "usable",
                "successful_channels": 2 if bad else 4, "attempted_channels": 4
            } for i in range(12)]
        self.assertEqual(evaluate(records()[:3], now=end)["status"], "insufficient")
        self.assertEqual(evaluate(records(), now=end)["status"], "candidate")
        self.assertEqual(evaluate(records(bad=True), now=end)["status"], "hold")

    def test_history(self):
        sample = {"observed_at": "2026-10-11T00:00:00+00:00", "source": "yxdr"}
        h = append_history({"samples": []}, sample)
        self.assertEqual(h["region"], "kua2")
        with self.assertRaises(ValueError):
            append_history(h, sample)


    def test_browser_five_channels_capture_wholesale_separately(self):
        """Browser fixture: 7881 has independent retail and wholesale categories."""
        import json
        from unittest.mock import patch
        from collector.collect import collect

        def channel(pf_id, coin_no, label):
            return {"data": json.dumps({
                "PfId": pf_id, "PfName": label, "GId": 1838, "CoinNo": coin_no
            }), "sign": f"{pf_id}-{coin_no}"}
        channels = [
            channel(30, "yxb", "YXB321"),
            channel(17, "yxb", "UU898"),
            channel(40, "yxb", "DD373"),
            channel(44, "yxbpf", "7881"),
            channel(44, "yxb", "7881"),
            channel(44, "wrong", "7881"),
        ]
        script = ("window.bijiaqiChanels=" + json.dumps(channels) + ";"
                  "window.bijiaqiResult=" + json.dumps({"GId": 1838, "GsId": 31}) + ";")
        requested = []
        def offer(url, amount, money):
            return {"BuyUrl": url, "Amount": amount, "Money": money,
                    "Price": money / amount}
        def fake_json(_opener, url, payload, _referer):
            if url.endswith("/coinsalesecret"):
                return {"time": "fixed-time", "secret": "fixed-secret"}
            params = json.loads(payload["data"])
            requested.append((params["PfId"], params["CoinNo"]))
            if params["PfId"] == 30:
                rows = []
            elif params["PfId"] == 17:
                rows = [offer("https://example.test/uu", 4000, 46)]
            elif params["PfId"] == 40:
                rows = [offer("https://example.test/dd", 550, 6.05)]
            elif params["CoinNo"] == "yxbpf":
                rows = [offer("https://example.test/bulk", 4000, 44)]
            else:
                rows = [offer("https://example.test/retail", 9000, 101)]
            return {"index": 0, "success": 1, "data": rows, "debug": None}
        with patch("collector.collect.fetch_text", side_effect=[
            '<script src="/js/CoinSale_yxb_example.js"></script>', script
        ]), patch("collector.collect.fetch_json", side_effect=fake_json), patch("collector.collect.time.sleep"):
            sample = collect({
                "id": "kua2", "source_url": "https://www.yxdr.com/bijiaqi/dnf/youxibi/kua2"
            })
        self.assertEqual(len(requested), 5)
        self.assertEqual([c for c in requested if c[0] == 44],
                         [(44, "yxbpf"), (44, "yxb")])
        self.assertEqual(sample["successful_channels"], 5)
        self.assertEqual(sample["successful_retail_platforms"], 4)
        self.assertEqual(sample["offers_count"], 3)
        self.assertEqual(sample["quality"], "partial")  # same >=5 retail threshold
        self.assertEqual(sample["wholesale_observation"]["offers_count"], 1)
        self.assertEqual(sample["wholesale_observation"]["best_ratio"], 90.9091)
        self.assertEqual(sample["best_ratio"], 90.9091)  # DD373 retail, not bulk
        self.assertEqual([c["coin_no"] for c in sample["channel_outcomes"] if c["id"] == 44],
                         ["yxbpf", "yxb"])

    def test_wholesale_success_never_upgrades_partial_retail_sample(self):
        import json
        from unittest.mock import patch
        from collector.collect import collect
        entries = [
            {"data": json.dumps({"PfId": 44, "PfName": "7881", "GId": 1838,
                                  "CoinNo": category}), "sign": category}
            for category in ("yxbpf", "yxb")
        ]
        script = ("window.bijiaqiChanels=" + json.dumps(entries) + ";"
                  "window.bijiaqiResult=" + json.dumps({"GId": 1838}) + ";")
        def fake_json(_opener, url, payload, _referer):
            if url.endswith("/coinsalesecret"):
                return {"time": "time", "secret": "secret"}
            category = json.loads(payload["data"])["CoinNo"]
            if category == "yxbpf":
                return {"success": 1, "data": [{"Price": 0.011, "Amount": 4000,
                                               "Money": 44, "BuyUrl": "https://example.test/w"}]}
            return {"success": 0, "data": None, "debug": None}
        with patch("collector.collect.fetch_text", side_effect=[
            '<script src="/js/CoinSale_yxb_example.js"></script>', script
        ]), patch("collector.collect.fetch_json", side_effect=fake_json), patch("collector.collect.time.sleep"):
            from collector.collect import collect
            with self.assertRaisesRegex(ValueError, "没有可核实库存"):
                collect({"id": "kua2", "source_url": "https://www.yxdr.com/bijiaqi/dnf/youxibi/kua2"})


if __name__ == "__main__":
    unittest.main()
