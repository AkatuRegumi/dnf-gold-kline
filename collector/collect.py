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
import re
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
        # Accept negotiates response format; do not claim to be Firefox.
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
        "Referer": referer,
        # Same-origin XHR POSTs carry an Origin header in actual browsers.
        # Keep our own explicit bot User-Agent; do not impersonate a browser.
        "Origin": BASE,
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


def classify_channel_response(response) -> str:
    """Return a conservative, explicitly evidenced error family."""
    if not isinstance(response, dict):
        return "unexpected_response"
    if response.get("success") in (True, 1, "true"):
        return "ok" if isinstance(response.get("data"), list) else "unexpected_response"
    debug = response.get("debug")
    message = debug[:2000].lower() if isinstance(debug, str) else ""
    # Only recognized words justify a category. A generic success=0 with
    # arbitrary debug text is not evidence of an access ban or rate limit.
    if re.search(r"429|rate.?limit|too many|throttl|限流|请求频繁|操作频繁", message):
        return "rate_limited"
    if re.search(r"captcha|forbidden|access denied|blocked|验证码|访问拒绝|403", message):
        return "access_restricted"
    if re.search(r"signat|invalid sign|签名|校验|token|secret|expired|过期|时间戳", message):
        return "request_validation_failed"
    if re.search(r"invalid param|bad request|参数错误|参数无效|参数异常", message):
        return "request_invalid"
    if re.search(r"timeout|temporar|upstream|超时|暂不可用|服务异常|502|503|504", message):
        return "upstream_unavailable"
    if re.search(r"no data|no offers|暂无数据|无数据|没有报价|无报价", message):
        return "no_offers_reported"
    return "unclassified_failure"


def safe_response_diagnostics(response) -> dict:
    """Bounded public diagnostics: never persist raw debug text or credentials.

    SHA-256 is solely an equality fingerprint to compare failure responses
    across runs. It is not used to authenticate or reverse-engineer a token.
    """
    if not isinstance(response, dict):
        return {"response_kind": type(response).__name__}
    debug = response.get("debug")
    record = {
        "response_kind": "json_object",
        "debug_kind": type(debug).__name__,
        "data_kind": type(response.get("data")).__name__,
    }
    if isinstance(debug, str) and debug:
        record["debug_chars"] = min(len(debug), 10000)
        record["debug_fingerprint"] = hashlib.sha256(
            debug.encode("utf-8", errors="replace")
        ).hexdigest()[:16]
    return record


def collect(region: dict) -> dict:
    region_id, url = region["id"], region["source_url"]
    cookie_jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookie_jar))
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
    token_acquired_at = time.monotonic()
    # A real browser may have a client cookie populated by JavaScript or an
    # earlier visit. urllib only receives cookies via Set-Cookie. We record
    # strictly its presence, never a cookie value or a synthesized token.
    site_client_cookie_present = any(
        cookie.name == "u_client" and cookie.domain.lstrip(".") in ("www.yxdr.com", "yxdr.com")
        for cookie in cookie_jar
    )
    print(f"[{region_id}] site_client_cookie_present={site_client_cookie_present}",
          flush=True)
    # Ordinary listings feed public K-line and depth estimates.
    # Wholesale (yxbpf) may have minimum-order restrictions or overlap retail stock;
    # preserve its observations separately rather than adding it to executable depth.
    rows, wholesale_rows, successes, attempts = [], [], 0, 0
    successful_retail_platforms: set[int] = set()
    contributing_retail_platforms: set[int] = set()
    channel_outcomes = []
    for channel in channels:
        pf_id = None
        coin_no = None
        try:
            params = json.loads(channel["data"])
            coin_no = params.get("CoinNo")
            if coin_no not in ("yxb", "yxbpf") or params.get("GId") != 1838:
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
            request_started_at = time.monotonic()
            token_age_s = round(max(0.0, request_started_at - token_acquired_at), 2)
            response = fetch_json(opener, BASE + "/bijia/coinsale", query, url)
            request_ms = round(max(0.0, time.monotonic() - request_started_at) * 1000)
            valid = isinstance(response, dict) and response.get("success") in (True, 1, "true")
            offers = response.get("data") if isinstance(response, dict) else None
            if valid and isinstance(offers, list):
                successes += 1
                if coin_no == "yxb":
                    successful_retail_platforms.add(pf_id)
                valid_count = 0
                destination = wholesale_rows if coin_no == "yxbpf" else rows
                for raw in offers:
                    if isinstance(raw, dict):
                        parsed = listing(raw, params.get("PfName", str(pf_id)))
                        if parsed:
                            destination.append(parsed)
                            valid_count += 1
                if coin_no == "yxb" and valid_count > 0:
                    contributing_retail_platforms.add(pf_id)
                channel_outcomes.append({
                    "id": pf_id, "coin_no": coin_no, "state": "ok",
                    "returned": len(offers), "accepted": valid_count,
                    "request_ms": request_ms, "token_age_s": token_age_s,
                })
            else:
                failure = {
                    "id": pf_id, "coin_no": coin_no,
                    "state": classify_channel_response(response),
                    "request_ms": request_ms, "token_age_s": token_age_s,
                    **safe_response_diagnostics(response),
                }
                channel_outcomes.append(failure)
                # Never log raw debug, signatures, request payloads or cookies.
                print(f"[{region_id}] channel={pf_id}/{coin_no} "
                      f"state={failure['state']} debug_kind={failure.get('debug_kind', 'none')} "
                      f"fingerprint={failure.get('debug_fingerprint', 'none')} "
                      f"age_s={token_age_s} request_ms={request_ms}", flush=True)
        except (ValueError, TypeError, KeyError, HTTPError, URLError, TimeoutError, OSError) as exc:
            if pf_id is not None:
                failure = {
                    "id": pf_id, "coin_no": coin_no,
                    "state": "request_error",
                    "error_kind": type(exc).__name__,
                }
                if isinstance(exc, HTTPError):
                    failure["http_status"] = exc.code
                channel_outcomes.append(failure)
            print(f"[{region_id}] channel error: {type(exc).__name__}", flush=True)
        time.sleep(0.5)
    if not successes:
        raise RuntimeError("没有任何成功的报价通道")
    summary = summarize(rows)
    # Only platforms with actual accepted retail listings count towards coverage.
    # An HTTP-successful but empty source is not independent market evidence.
    quality = ("usable" if len(contributing_retail_platforms) >= 2
               and summary["offers_count"] >= 5 else "partial")
    wholesale = summarize(wholesale_rows) if wholesale_rows else None
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quality": quality,
        "source": "yxdr", "market": "listed_asks", "region": region_id,
        "source_url": url,
        "site_client_cookie_present": site_client_cookie_present,
        "successful_channels": successes, "attempted_channels": attempts,
        "successful_retail_platforms": len(successful_retail_platforms),
        "contributing_retail_platforms": len(contributing_retail_platforms),
        "failed_channels": attempts - successes,
        "channel_outcomes": channel_outcomes,
        "wholesale_observation": (
            {"offers_count": wholesale["offers_count"],
             "best_ratio": wholesale["best_ratio"],
             "market": "listed_wholesale_asks"} if wholesale is not None else None
        ),
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
                 quality: str | None = None, reason: str | None = None,
                 sample: dict | None = None) -> None:
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
    if sample is not None and outcome == "success":
        record["offers_count"] = int(sample.get("offers_count", 0))
        record["successful_channels"] = int(sample.get("successful_channels", 0))
        record["attempted_channels"] = int(sample.get("attempted_channels", 0))
        record["channel_outcomes"] = sample.get("channel_outcomes", [])
        record["site_client_cookie_present"] = sample.get("site_client_cookie_present")
        record["successful_retail_platforms"] = sample.get("successful_retail_platforms")
        record["contributing_retail_platforms"] = sample.get("contributing_retail_platforms")
        wholesale = sample.get("wholesale_observation")
        record["wholesale_offers_count"] = (wholesale or {}).get("offers_count", 0)
    status["regions"][region_id] = record
    # Keep a short rolling, append-only diagnostic history for frequency decisions.
    history = status.setdefault("history", {})
    if not isinstance(history, dict):
        raise ValueError("invalid collection status history")
    history.setdefault(region_id, []).append(dict(record))
    history[region_id] = history[region_id][-40:]
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
            save_attempt(region_id, "success", data_dir, quality=sample.get("quality"), sample=sample)
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
    """Three staggered groups, each scheduled once per UTC hour."""
    if requested == "all":
        return options
    if requested in ("group0", "group1", "group2"):
        slot = int(requested[-1])
        return [item for i, item in enumerate(options) if i % 3 == slot]
    if requested == "scheduled":
        # Manual/push fallback only; scheduled Actions pin groups to cron identity.
        # UTC minutes :07, :27 and :47 correspond to groups 0, 1 and 2.
        stamp = now if now is not None else datetime.now(timezone.utc)
        slot = stamp.astimezone(timezone.utc).minute // 20
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
