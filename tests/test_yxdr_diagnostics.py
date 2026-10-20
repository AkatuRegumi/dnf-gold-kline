"""Contract checks against redacted 2026-10-20 browser response samples.

No live network, credentials, raw debug messages, or persistent market writes.
The rows below retain real Amount/Money/Price field combinations the user saw;
IDs are local fixture IDs, not live seller URLs.
"""
import io
import json
import unittest
from unittest.mock import patch

from collector.collect import (
    classify_channel_response, collect, fetch_json, safe_response_diagnostics,
)
from collector.market import BASE


class BrowserResponseRegressionTest(unittest.TestCase):
    def test_same_origin_json_request_has_intentional_headers(self):
        class Opener:
            request = None

            def open(self, request, timeout):
                self.request = request
                self.timeout = timeout
                return io.BytesIO(b'{"success":1,"data":[]}')

        opener = Opener()
        result = fetch_json(
            opener, BASE + "/bijia/coinsale", {"data": "example"}, 
            BASE + "/bijiaqi/dnf/youxibi/kua2"
        )
        self.assertEqual(result["success"], 1)
        self.assertEqual(opener.request.get_header("Origin"), BASE)
        self.assertEqual(opener.request.get_header("Referer"), BASE + "/bijiaqi/dnf/youxibi/kua2")
        self.assertIn("DNF-Gold-Kline", opener.request.get_header("User-agent"))
        self.assertEqual(opener.timeout, 20)

    def test_error_families_never_dump_opaque_response(self):
        raw = "validation failed secret=PRIVATE_AND_SENSITIVE sign=OTHER_SECRET"
        response = {"index": 0, "success": 0, "data": None, "debug": raw}
        self.assertEqual(classify_channel_response(response), "request_validation_failed")
        details = safe_response_diagnostics(response)
        self.assertEqual(details["debug_kind"], "str")
        self.assertEqual(details["debug_chars"], len(raw))
        self.assertEqual(len(details["debug_fingerprint"]), 16)
        self.assertNotIn("PRIVATE", json.dumps(details))
        self.assertEqual(classify_channel_response({"success": 0, "debug": "not explained"}),
                         "unclassified_failure")
        self.assertEqual(classify_channel_response({"success": 0, "debug": "too many requests"}),
                         "rate_limited")
        self.assertEqual(classify_channel_response({"success": 0, "debug": "参数错误"}),
                         "request_invalid")
        self.assertEqual(classify_channel_response({"success": 1, "data": None}),
                         "unexpected_response")
        self.assertEqual(safe_response_diagnostics(["not a dict"]),
                         {"response_kind": "list"})

    def test_browser_dd373_7881_and_uu898_rows_are_retained(self):
        """Proof that real-format browser rows pass ordinary/wholesale routing."""
        def ch(pid, category, name):
            return {"data": json.dumps({
                "PfId": pid, "PfName": name, "GId": 1838, "CoinNo": category,
            }), "sign": str(pid) + category}
        channels = [
            ch(30, "yxb", "empty"),
            ch(17, "yxb", "UU898"),
            ch(40, "yxb", "DD373"),
            ch(44, "yxbpf", "7881"),
            ch(44, "yxb", "7881"),
        ]
        script = ("window.bijiaqiChanels=" + json.dumps(channels) + ";"
                  "window.bijiaqiResult=" + json.dumps({"GId": 1838, "GsId": 150}) + ";")
        rows = {
            (30, "yxb"): [],
            (17, "yxb"): [
                (0.01123, 40000, 449.2), (0.011235, 10000, 112.35),
                (0.011236, 19000, 213.48), (0.011236, 33400, 375.28),
            ],
            (40, "yxb"): [
                (0.011494, 102037, 1172.81), (0.01126, 3500, 39.41),
                (0.0113, 2000, 22.6),
            ],
            (44, "yxb"): [
                (0.011364, 2200, 25.0), (0.011374, 40000, 454.95),
                (0.011382, 2750, 31.30),
            ],
            (44, "yxbpf"): [
                (0.011558, 100000, 1155.76), (0.011558, 150000, 1733.65),
            ],
        }
        observed = []
        def fake_json(_opener, url, payload, _referer):
            if url.endswith("/coinsalesecret"):
                return {"time": "test-time", "secret": "test-secret"}
            params = json.loads(payload["data"])
            platform_key = (params["PfId"], params["CoinNo"])
            observed.append(platform_key)
            offers = [
                {"Price": price, "Amount": amount, "Money": money,
                 "BuyUrl": "https://example.invalid/" + str(platform_key[0]) + "/" +
                           platform_key[1] + "/" + str(i)}
                for i, (price, amount, money) in enumerate(rows[platform_key])
            ]
            return {"index": 0, "success": 1, "data": offers, "debug": None}

        with patch("collector.collect.fetch_text", side_effect=[
            '<script src="/js/CoinSale_yxb_fixture.js"></script>', script,
        ]), patch("collector.collect.fetch_json", side_effect=fake_json), patch(
            "collector.collect.time.sleep"
        ):
            sample = collect({"id": "kua2", "source_url": BASE + "/bijiaqi/dnf/youxibi/kua2"})

        self.assertEqual(len(observed), 5)
        self.assertEqual(sample["quality"], "usable")
        self.assertEqual(sample["offers_count"], 10)
        self.assertEqual(sample["contributing_retail_platforms"], 3)
        self.assertEqual(sample["successful_retail_platforms"], 4)
        self.assertEqual(sample["wholesale_observation"]["offers_count"], 2)
        self.assertEqual(
            {(x["id"], x["coin_no"]): x["accepted"] for x in sample["channel_outcomes"]},
            {(30, "yxb"): 0, (17, "yxb"): 4, (40, "yxb"): 3, 
             (44, "yxbpf"): 2, (44, "yxb"): 3},
        )

    def test_unexpected_non_object_failure_does_not_crash_collection(self):
        channels = [
            {"data": json.dumps({"PfId": 17, "PfName": "UU898", "GId": 1838, "CoinNo": "yxb"}),
             "sign": "17"},
            {"data": json.dumps({"PfId": 40, "PfName": "DD373", "GId": 1838, "CoinNo": "yxb"}),
             "sign": "40"},
        ]
        script = ("window.bijiaqiChanels=" + json.dumps(channels) + ";"
                  "window.bijiaqiResult=" + json.dumps({"GId": 1838}) + ";")
        def fake_json(_opener, url, payload, _referer):
            if url.endswith("/coinsalesecret"):
                return {"time": "test", "secret": "test"}
            if json.loads(payload["data"])["PfId"] == 40:
                return ["bad payload"]
            return {"success": 1, "data": [
                {"Price": 0.011, "Amount": 10000, "Money": 110,
                 "BuyUrl": "https://example.invalid/uu"}
            ]}
        with patch("collector.collect.fetch_text", side_effect=[
            '<script src="/js/CoinSale_yxb_fixture.js"></script>', script,
        ]), patch("collector.collect.fetch_json", side_effect=fake_json), patch(
            "collector.collect.time.sleep"
        ):
            sample = collect({"id": "kua2", "source_url": BASE + "/bijiaqi/dnf/youxibi/kua2"})
        self.assertEqual(sample["channel_outcomes"][1]["state"], "unexpected_response")
        self.assertEqual(sample["channel_outcomes"][1]["response_kind"], "list")
        self.assertEqual(sample["quality"], "partial")


if __name__ == "__main__":
    unittest.main()
