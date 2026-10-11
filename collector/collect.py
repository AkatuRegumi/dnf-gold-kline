"""Low-frequency collection of public YXDR listing quotes for all DNF cross-regions.

Each region has its own history. A failed region never changes its history.
No authentication, no captcha bypass, and no fabricated samples.
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

from collector.market import BASE, script_url, assignment, listing, summarize, append_history

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "docs" / "data" / "regions.json"
DATA_DIR = ROOT / "docs" / "data"


def regions() -> list[dict]:
    config = json.loads(REGISTRY.read_text(encoding="utf-8"))
    items = config["regions"]
    ids = [item["id"] for item in items]
    if len(ids) != 9 or len(set(ids)) != 9:
        raise ValueError("跨区配置不完整或重复")
    for item in items:
        if not item["source_url"] == BASE + "/bijiaqi/dnf/youxibi/" + item["id"]:
            raise ValueError("跨区数据源必须是游戏达人官方跨区报价页面")
    return items


def fetch_json(opener, url: str, payload: dict, referer: str):
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": referer,
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (compatible; DNF-Gold-Kline/0.2)",
    })
    with opener.open(request, timeout=20) as response:
        return json.load(response)


def fetch_text(opener, url: str):
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; DNF-Gold-Kline/0.2)",
        "Accept": "text/html,application/javascript,*/*",
    })
    with opener.open(request, timeout=20) as response:
        return response.read(5_000_000).decode("utf-8-sig", "replace")


def collect(region: dict) -> dict:
    region_id, url = region["id"], region["source_url"]
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    html = fetch_text(opener, url)
    script = fetch_text(opener, script_url(html))
    channels = assignment(script, "bijiaqiChanels")
    meta = assignment(script, "bijiaqiResult")
    if not isinstance(channels, list) or not isinstance(meta, dict) or meta.get("GId") != 1838:
        raise RuntimeError("游戏类型或上游通道数据格式已变化")
    token = fetch_json(opener, BASE + "/bijia/coinsalesecret",
                       {"GId": 1838, "GsId": meta.get("GsId")}, url)
    if not isinstance(token, dict) or not token.get("time") or not token.get("secret"):
        raise RuntimeError("未取得上游公开页面请求校验信息")
    rows, successes, attempts = [], 0, 0
    for channel in channels:
        try:
            params = json.loads(channel["data"])
            if params.get("CoinNo") != "yxb" or params.get("GId") != 1838:
                continue
            pf_id = int(params["PfId"])
            attempts += 1
            channel_sign = channel["sign"]
            digest = hashlib.md5(
                f'{token["secret"]}_{pf_id}_{channel_sign}'.encode("utf-8")
            ).hexdigest()
            query = {
                "data": channel["data"], "sign": channel_sign,
                "cross": 0, "dnfCross": 1,
                "time": token["time"], "secret": digest,
            }
            response = fetch_json(opener, BASE + "/bijia/coinsale", query, url)
            valid = isinstance(response, dict) and response.get("success") in (True, 1, "true")
            offers = response.get("data") if isinstance(response, dict) else None
            if valid and isinstance(offers, list):
                successes += 1
                for raw in offers:
                    if isinstance(raw, dict):
                        parsed = listing(raw, params.get("PfName", str(pf_id)))
                        if parsed:
                            rows.append(parsed)
            else:
                # Safe structural diagnostics only; never log signatures, IDs or raw payloads.
                outcome = str(response.get("success"))[:12] if isinstance(response, dict) else "non-dict"
                payload_kind = type(offers).__name__
                payload_size = len(offers) if isinstance(offers, list) else 0
                print(f"[{region_id}] channel={pf_id} unavailable success={outcome} data={payload_kind} count={payload_size}")
        except (ValueError, TypeError, KeyError, HTTPError, URLError, TimeoutError, OSError) as exc:
            print(f"[{region_id}] channel error: {type(exc).__name__}")
        time.sleep(0.5)
    if not successes:
        raise RuntimeError("没有任何成功的报价通道")
    summary = summarize(rows)
    # Heuristic only: non-comprehensive partial coverage remains a real sample.
    quality = "usable" if successes >= 2 and summary["offers_count"] >= 5 else "partial"
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quality": quality,
        "source": "yxdr", "market": "listed_asks", "region": region_id,
        "source_url": url,
        "successful_channels": successes, "attempted_channels": attempts,
        "failed_channels": attempts - successes,
        **summary,
    }


def save_sample(region_id: str, sample: dict, data_dir: Path = DATA_DIR) -> None:
    path = data_dir / f"{region_id}.json"
    history = (json.loads(path.read_text(encoding="utf-8")) if path.exists()
               else {"schema_version": 1, "region": region_id, "samples": []})
    updated = append_history(history, sample, region_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def save_attempt(region_id: str, outcome: str, data_dir: Path = DATA_DIR, *,
                 quality: str | None = None, reason: str | None = None) -> None:
    """Persist collection health separately; never invent or mutate market samples."""
    if outcome not in ("success", "failed"):
        raise ValueError("invalid collection outcome")
    path = data_dir / "collection_status.json"
    status = (json.loads(path.read_text(encoding="utf-8")) if path.exists()
              else {"schema_version": 1, "regions": {}})
    if status.get("schema_version") != 1 or not isinstance(status.get("regions"), dict):
        raise ValueError("invalid collection status schema")
    record = {
        "attempted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "outcome": outcome,
    }
    if outcome == "success" and quality in ("usable", "partial"):
        record["quality"] = quality
    if outcome == "failed":
        record["reason"] = (reason or "unknown collection error")[:160]
    status["regions"][region_id] = record
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def error_reason(exc: Exception) -> str:
    """Keep the public health record useful without storing URLs or credentials."""
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, URLError):
        return "upstream network error"
    if isinstance(exc, (ValueError, RuntimeError, KeyError, json.JSONDecodeError)):
        return f"{type(exc).__name__}: {str(exc)[:130]}"
    return type(exc).__name__


def run(selected: list[dict], data_dir: Path = DATA_DIR) -> tuple[int, int]:
    passed, failed = 0, 0
    for index, region in enumerate(selected):
        if index:
            time.sleep(2)  # space out requests across regions
        region_id = region["id"]
        try:
            sample = collect(region)
            save_sample(region_id, sample, data_dir)
            save_attempt(region_id, "success", data_dir, quality=sample.get("quality"))
            passed += 1
            print(f'[{region_id}] saved: quality={sample.get("quality", "unknown")} '
                  f'best={sample.get("best_ratio", "?")} offers={sample.get("offers_count", "?")} '
                  f'channels={sample.get("successful_channels", "?")}/{sample.get("attempted_channels", "?")}', flush=True)
        except (ValueError, RuntimeError, HTTPError, URLError, TimeoutError, OSError,
                KeyError, json.JSONDecodeError) as exc:
            failed += 1
            reason = error_reason(exc)
            save_attempt(region_id, "failed", data_dir, reason=reason)
            print(f"[{region_id}] failed: {reason}", flush=True)
    return passed, failed


def pick_regions(options: list[dict], requested: str, now: datetime | None = None) -> list[dict]:
    """Three staggered groups, each polled twice per UTC day at 4-hour intervals."""
    if requested == "all":
        return options
    if requested in ("group0", "group1", "group2"):
        slot = int(requested[-1])
        return [item for i, item in enumerate(options) if i % 3 == slot]
    if requested == "scheduled":
        # Manual/push fallback only; scheduled Actions pin groups to cron identity.
        stamp = now if now is not None else datetime.now(timezone.utc)
        slot = (stamp.astimezone(timezone.utc).hour // 4) % 3
        return [item for i, item in enumerate(options) if i % 3 == slot]
    return [item for item in options if item["id"] == requested]


def main() -> None:
    options = regions()
    parser = argparse.ArgumentParser(description="Capture real DNF market quotes by cross-region")
    parser.add_argument("--region", default="scheduled",
                        choices=["scheduled", "all", "group0", "group1", "group2"] + [r["id"] for r in options])
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    selected = pick_regions(options, args.region)
    print("selected regions: " + ", ".join(r["id"] for r in selected), flush=True)
    passed, failed = run(selected, args.data_dir)
    print(f"regions: saved={passed}, failed={failed}", flush=True)
    if passed == 0:
        raise SystemExit("No successful region snapshots; existing data was preserved.")


if __name__ == "__main__":
    main()
