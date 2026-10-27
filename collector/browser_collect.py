"""Canonical browser-rendered YXDR capture for DNF retail gold price snapshots.

One ordinary page load per region. No OCR, browser impersonation, request
retries, stored sessions, synthetic quotes or shared user cookies. The browser
may render mixed categories from 7881; the latter is diagnostic only until a
trusted DOM field distinguishes its ordinary/wholesale listings.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import time

from playwright.sync_api import TimeoutError as BrowserTimeout, sync_playwright

from collector.collect import DATA_DIR, pick_regions, regions, save_attempt, save_sample
from collector.market import BASE, summarize
from tools.probe_yxdr_dom import EXTRACT_DOM, parse_rows

# Verified by the existing upstream channel metadata as ordinary game-coin
# sources. Provider 44 (7881) may be retail or wholesale in this *merged* DOM.
KNOWN_ORDINARY = {"17": "UU898", "40": "DD373", "30": "YXB321"}


def snapshot_from_dom(region: dict, capture: dict, *,
                      captured_at: str | None = None) -> dict:
    """Convert rendered data without pretending mixed DOM entries are retail."""
    parsed = parse_rows(capture, limit=1000)
    ordinary = []
    platform_counts: dict[str, int] = {}
    for entry in parsed["top"]:
        pid = entry["platform_id"]
        if pid not in KNOWN_ORDINARY:
            continue
        platform_counts[pid] = platform_counts.get(pid, 0) + 1
        ordinary.append({
            "platform": KNOWN_ORDINARY[pid],
            "ratio": entry["ratio"],
            "available_wan": entry["amount_wan"],
            "lot_cny": entry["money_cny"],
            # A DOM quote lacks a verified individual inventory ID. Dedup by
            # platform, quantity, price in the ordinary summary function.
            "id": "",
        })
    summary = summarize(ordinary)
    contributing = len(platform_counts)
    platform_ids = sorted(parsed["platforms"], key=int)
    channel_outcomes = [
        {
            "id": int(pid),
            "coin_no": "yxb" if pid in KNOWN_ORDINARY else "unknown",
            "state": "ok" if pid in KNOWN_ORDINARY else "mixed_category_unverified",
            "returned": parsed["platforms"][pid],
            "accepted": platform_counts.get(pid, 0),
        }
        for pid in platform_ids
    ]
    quality = ("usable" if contributing >= 2 and summary["offers_count"] >= 5 else "partial")
    return {
        "observed_at": captured_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "region": region["id"],
        "source_url": region["source_url"],
        "source": "yxdr", "capture_method": "rendered_dom",
        "market": "listed_asks",
        "quality": quality,
        "successful_channels": contributing,
        # No direct per-platform API requests occur in this capture mode.
        "attempted_channels": contributing,
        "failed_channels": 0,
        "successful_retail_platforms": contributing,
        "contributing_retail_platforms": contributing,
        "channel_outcomes": channel_outcomes,
        "wholesale_observation": None,
        "rendered_observation": {
            "total_visible_rows": parsed["visible_rows"],
            "validated_rows": parsed["accepted_rows"],
            "platform_counts": parsed["platforms"],
            "ambiguous_category_rows": sum(
                count for pid, count in parsed["platforms"].items()
                if pid not in KNOWN_ORDINARY
            ),
            "top_displayed_ratio": (
                max(row["ratio"] for row in parsed["top"])
                if parsed["top"] else None
            ),
        },
        **summary,
    }


def collect_browser(region: dict, browser) -> dict:
    url = region["source_url"]
    if not url.startswith(BASE + "/bijiaqi/dnf/youxibi/"):
        raise ValueError("Unexpected upstream page")
    context = browser.new_context(locale="zh-CN", viewport={"width": 1440, "height": 900})
    try:
        page = context.new_page()
        response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if response is None or response.status != 200:
            raise RuntimeError("The YXDR quote page did not return HTTP 200")
        try:
            page.wait_for_function(
                "() => [...document.querySelectorAll('#result_m .list_m .body')].some(r => "
                "r.querySelector('.item3')?.textContent?.trim() && "
                "r.querySelector('.item4')?.textContent?.trim())",
                timeout=20000,
            )
        except BrowserTimeout as exc:
            raise RuntimeError("No rendered price rows in the ordinary-quote DOM") from exc
        page.wait_for_timeout(3500)  # allow later asynchronously loaded platforms to appear
        capture = page.evaluate(EXTRACT_DOM)
        sample = snapshot_from_dom(region, capture)
        print(
            f"[{region['id']}] DOM visible={sample['rendered_observation']['total_visible_rows']}"
            f" providers={sample['rendered_observation']['platform_counts']}"
            f" ordinary={sample['offers_count']}"
            f" excluded_mixed={sample['rendered_observation']['ambiguous_category_rows']}"
            f" quality={sample['quality']}", flush=True,
        )
        return sample
    finally:
        context.close()


def run(selected: list[dict], data_dir=DATA_DIR) -> tuple[int, int]:
    passed, failed = 0, 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        try:
            for i, region in enumerate(selected):
                if i:
                    time.sleep(2)
                try:
                    sample = collect_browser(region, browser)
                    save_sample(region["id"], sample, data_dir)
                    save_attempt(region["id"], "success", data_dir,
                                 quality=sample["quality"], sample=sample)
                    passed += 1
                except Exception as exc:
                    # Never log browser request URLs, request headers, cookies,
                    # raw page errors or signed payloads.
                    failed += 1
                    reason = type(exc).__name__
                    save_attempt(region["id"], "failed", data_dir, reason=reason)
                    print(f"[{region['id']}] browser capture failed: {reason}", flush=True)
        finally:
            browser.close()
    return passed, failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture YXDR prices from rendered page DOM")
    options = regions()
    parser.add_argument("--region", default="scheduled",
                        choices=["scheduled", "all", "group0", "group1", "group2"] +
                        [region["id"] for region in options])
    parser.add_argument("--data-dir", type=str, default=str(DATA_DIR))
    parser.add_argument("--dry-run", action="store_true",
                        help="Read one selected region without writing market history")
    args = parser.parse_args()
    from pathlib import Path
    selected = pick_regions(options, args.region)
    if args.dry_run:
        if len(selected) != 1:
            parser.error("--dry-run requires exactly one specific region")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            try:
                sample = collect_browser(selected[0], browser)
            finally:
                browser.close()
        print("YXDR_BROWSER_DRY_RUN " + json.dumps({
            "region": sample["region"], "quality": sample["quality"],
            "offers_count": sample["offers_count"],
            "platform_counts": sample["rendered_observation"]["platform_counts"],
            "excluded_mixed": sample["rendered_observation"]["ambiguous_category_rows"],
            "best_ratio": sample["best_ratio"],
        }, ensure_ascii=False), flush=True)
        raise SystemExit(0 if sample["quality"] == "usable" else 2)
    print("browser-rendered regions: " + ", ".join(r["id"] for r in selected), flush=True)
    passed, failed = run(selected, Path(args.data_dir))
    print(f"browser regions: saved={passed}, failed={failed}", flush=True)
    if passed == 0:
        raise SystemExit("No rendered quotes saved; existing history preserved.")


if __name__ == "__main__":
    main()
