"""One-shot, read-only browser-rendered YXDR quote probe.

Experimental diagnostic only: NO data persistence, retries, auth, cookie export,
proxy rotation, browser fingerprint spoofing or scheduler changes.

Run: python -m tools.probe_yxdr_dom --region kua2 --min-platforms 2
The script emits aggregate counts and up to 10 rounded, displayed prices.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import re

from collector.collect import regions
from collector.market import BASE

# Matches the real client-side markup examined in Firefox by the user.
ROW_SELECTOR = "#result_m .list_m .body"

EXTRACT_DOM = r"""() => {
  const rows = [...document.querySelectorAll('#result_m .list_m .body')];
  const visible = rows.filter(row => row.getClientRects().length > 0);
  return {
    total: rows.length,
    visible: visible.length,
    rows: visible.map(row => {
      const value = selector => row.querySelector(selector)?.textContent?.trim() ?? '';
      const platformElement = row.querySelector('[class*="platform_"]');
      const platformClass = [...(platformElement?.classList ?? [])]
        .find(cls => /^platform_\d+$/.test(cls)) ?? '';
      return {
        displayed: value('.item1'),
        amount: value('.item3'),
        money: value('.item4'),
        platform_id: platformClass ? platformClass.slice(9) : '',
        platform_label: platformElement?.textContent?.trim() ?? ''
      };
    })
  };
}"""


def _numeric(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    raw = value.strip().replace(",", "")
    if not re.fullmatch(r"\d+(?:\.\d+)?", raw):
        return None
    result = float(raw)
    return result if math.isfinite(result) else None


def parse_rows(capture: dict, limit: int = 10) -> dict:
    """Parse displayed ordinary-retail lots; count vendors *before* truncation.

    Never assume that the first visible lot is a complete multi-platform quote.
    """
    rows = capture.get("rows", [])
    if not isinstance(rows, list):
        rows = []
    accepted = []
    platforms = Counter()
    rejected = 0
    for row in rows:
        if not isinstance(row, dict):
            rejected += 1
            continue
        amount = _numeric(row.get("amount"))
        money = _numeric(row.get("money"))
        pid = str(row.get("platform_id") or "").strip()
        shown = str(row.get("displayed") or "").strip()
        if amount is None or money is None or amount <= 0 or money < 5 or not pid.isdigit():
            rejected += 1
            continue
        ratio = amount / money
        if not (30 <= ratio <= 150 and math.isfinite(ratio)):
            rejected += 1
            continue
        # The page displays 'CNY per 10k / 10k per CNY'. Confirm the unit.
        # UI output is rounded, so use a small tolerance, not exact equality.
        if "/" in shown:
            shown_ratio = _numeric(shown.split("/")[-1])
            if shown_ratio is None or abs(shown_ratio - ratio) > 0.25:
                rejected += 1
                continue
        accepted.append({"platform_id": pid, "ratio": round(ratio, 4),
                         "amount_wan": amount, "money_cny": money})
        platforms[pid] += 1
    return {
        "dom_total_rows": int(capture.get("total", 0)),
        "visible_rows": int(capture.get("visible", 0)),
        "accepted_rows": len(accepted),
        "discarded_rows": rejected,
        "platforms": dict(sorted(platforms.items())),
        "platform_count": len(platforms),
        "top": accepted[:limit],
    }


def run(region_id: str, min_platforms: int) -> int:
    from playwright.sync_api import TimeoutError as BrowserTimeout, sync_playwright

    choices = {r["id"]: r["source_url"] for r in regions()}
    if region_id not in choices:
        raise ValueError("Unknown configured DNF region")
    url = choices[region_id]
    if not url.startswith(BASE + "/bijiaqi/dnf/youxibi/"):
        raise ValueError("Unexpected upstream URL")
    report = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "probe": "read_only_dom",
        "region": region_id,
        "url": url,
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        try:
            page = browser.new_page(locale="zh-CN", viewport={"width": 1440, "height": 900})
            page.set_default_timeout(20000)
            errors = []
            # DO NOT inspect or log response bodies, cookies, secret fields or signed requests.
            page.on("requestfailed", lambda req: errors.append(
                "failed_resource" if req.url.startswith(BASE + "/") else "failed_other"
            ))
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                report["http_status"] = response.status if response else None
                page.wait_for_function(
                    "() => [...document.querySelectorAll('#result_m .list_m .body')].some(r => "
                    "r.querySelector('.item3')?.textContent?.trim() && "
                    "r.querySelector('.item4')?.textContent?.trim())",
                    timeout=20000,
                )
                # One page load, no retry. Allow normal asynchronous lists to settle.
                page.wait_for_timeout(3500)
                report["load_state"] = "rows_rendered"
            except BrowserTimeout:
                report["load_state"] = "timed_out"
            except Exception as exc:
                report["load_state"] = "navigation_error"
                report["error_kind"] = type(exc).__name__
            summary = parse_rows(page.evaluate(EXTRACT_DOM))
            report.update(summary)
            report["failed_resource_requests"] = len(errors)
            report["result"] = (
                "multi_platform" if summary["platform_count"] >= min_platforms and
                summary["accepted_rows"] >= 5 else
                "insufficient_dom_coverage"
            )
            # Output safe numbers; no seller URLs, cookies, raw HTML, request contents.
            print("YXDR_DOM_PROBE " + json.dumps(report, ensure_ascii=False))
            return 0 if report["result"] == "multi_platform" else 2
        finally:
            browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="kua2")
    parser.add_argument("--min-platforms", type=int, default=2)
    args = parser.parse_args()
    raise SystemExit(run(args.region, args.min_platforms))


if __name__ == "__main__":
    main()
