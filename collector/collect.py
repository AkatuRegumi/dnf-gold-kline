"""Collect public cross-two game-gold seller quotes at low frequency.

No login/session-token reuse, no captcha bypass or retry storms.
No successful observation means no historical write.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPCookieProcessor

from collector.market import BASE, CROSS_2, script_url, assignment, listing, summarize, append_history

OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "data" / "history.json"


def fetch_json(opener, url: str, payload: dict, referer: str):
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": referer,
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (compatible; DNF-Gold-Kline/0.1)",
    })
    with opener.open(request, timeout=20) as response:
        return json.load(response)


def fetch_text(opener, url: str):
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; DNF-Gold-Kline/0.1)",
        "Accept": "text/html,application/javascript,*/*",
    })
    with opener.open(request, timeout=20) as response:
        return response.read(5_000_000).decode("utf-8-sig", "replace")


def collect() -> dict:
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    html = fetch_text(opener, CROSS_2)
    script = fetch_text(opener, script_url(html))
    channels = assignment(script, "bijiaqiChanels")
    meta = assignment(script, "bijiaqiResult")
    if not isinstance(channels, list) or not isinstance(meta, dict):
        raise RuntimeError("上游通道数据格式已变化")
    token = fetch_json(opener, BASE + "/bijia/coinsalesecret",
                       {"GId": meta.get("GId", 1838), "GsId": meta.get("GsId")}, CROSS_2)
    if not isinstance(token, dict) or not token.get("time") or not token.get("secret"):
        raise RuntimeError("上游未返回可用请求校验信息")
    rows, successes = [], 0
    candidate_channels = 0
    rejected_channels = 0
    print(f"diagnostic: configured_channels={len(channels)}", flush=True)
    for channel in channels:
        try:
            params = json.loads(channel["data"])
            if params.get("CoinNo") != "yxb":
                continue
            platform_id = int(params["PfId"])
            candidate_channels += 1
            channel_sign = channel["sign"]
            signature = hashlib.md5(
                f'{token["secret"]}_{platform_id}_{channel_sign}'.encode("utf-8")
            ).hexdigest()
            query = {
                "data": channel["data"], "sign": channel_sign,
                "cross": 0, "dnfCross": 1,
                "time": token["time"], "secret": signature,
            }
            result = fetch_json(opener, BASE + "/bijia/coinsale", query, CROSS_2)
            valid = isinstance(result, dict) and result.get("success") in (True, 1, "true")
            offers = result.get("data") if isinstance(result, dict) else None
            if valid and isinstance(offers, list):
                successes += 1
                for offer in offers:
                    if isinstance(offer, dict):
                        row = listing(offer, params.get("PfName", str(platform_id)))
                        if row:
                            rows.append(row)
            else:
                rejected_channels += 1
                kind = type(result).__name__
                status = result.get("success") if isinstance(result, dict) else None
                data_kind = type(offers).__name__
                print(f"diagnostic: channel={platform_id} reply_type={kind} "
                      f"success={str(status)[:30]} data_type={data_kind}", flush=True)
        except (ValueError, TypeError, KeyError, HTTPError, URLError, TimeoutError, OSError) as exc:
            print(f"warning: channel failed: {type(exc).__name__}: {exc}")
        time.sleep(0.5)
    print(f"diagnostic: candidate_channels={candidate_channels} "
          f"successful_channels={successes} rejected_channels={rejected_channels} "
          f"valid_rows={len(rows)}", flush=True)
    if successes == 0:
        raise RuntimeError("没有成功的公开报价通道，拒绝写入假数据")
    summary = summarize(rows)
    quality = "usable" if successes >= 3 and summary["offers_count"] >= 10 else "partial"
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quality": quality,
        "source": "yxdr", "market": "listed_asks", "region": "kua2",
        "source_url": CROSS_2, "successful_channels": successes,
        "attempted_channels": candidate_channels,
        "failed_channels": candidate_channels - successes,
        **summary,
    }


def main():
    parser = argparse.ArgumentParser(description="Capture a DNF cross-two quote snapshot")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    sample = collect()
    history = (json.loads(args.output.read_text(encoding="utf-8"))
               if args.output.exists() else {"samples": []})
    result = append_history(history, sample)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, args.output)
    print(f'Saved {sample["observed_at"]} best={sample["best_ratio"]} '
          f'offers={sample["offers_count"]} channels={sample["successful_channels"]}')


if __name__ == "__main__":
    main()
