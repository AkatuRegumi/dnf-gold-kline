"""One-shot comparison of the public YXDR page in a normal Chrome session.
No login, request alteration, auth replay, or raw credential/payload logging.
Run in GitHub Actions only when explicitly invoked / this file changes.
"""
from __future__ import annotations

import json
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

URL = "https://www.yxdr.com/bijiaqi/dnf/youxibi/kua7"


def safe_channel(request):
    try:
        payload = request.post_data_json
        if not isinstance(payload, dict):
            return {"payload": type(payload).__name__}
        inner = json.loads(payload.get("data", "{}"))
        return {
            "pf_id": inner.get("PfId"),
            "pf_name": inner.get("PfName"),
            "cross": payload.get("cross"),
            "dnfCross": payload.get("dnfCross"),
            "payload_keys": sorted(payload.keys()),
        }
    except (ValueError, TypeError, AttributeError):
        return {"payload": "unreadable"}


def main():
    observed = []
    with sync_playwright() as playwright:
        # Use standard Chrome with its normal defaults, not anti-bot evasions.
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page()

        def on_response(response):
            path = urlparse(response.url).path.lower()
            if not path.endswith("/bijia/coinsale"):
                return
            record = {"http": response.status, **safe_channel(response.request)}
            try:
                headers = response.request.all_headers()
                record["request_headers"] = {
                    "content_type": headers.get("content-type"),
                    "accept": headers.get("accept"),
                    "origin": headers.get("origin"),
                    "referer_domain": urlparse(headers.get("referer", "")).netloc,
                    "x_requested_with": headers.get("x-requested-with"),
                    "has_cookie": bool(headers.get("cookie")),
                    "chrome_user_agent": "Chrome/" in headers.get("user-agent", ""),
                }
            except Exception as exc:
                record["header_error"] = type(exc).__name__
            try:
                obj = response.json()
                if isinstance(obj, dict):
                    rows = obj.get("data")
                    record.update({
                        "success": obj.get("success"),
                        "data_type": type(rows).__name__,
                        "rows": len(rows) if isinstance(rows, list) else None,
                        "response_keys": sorted(obj.keys()),
                        "code": obj.get("code") if isinstance(obj.get("code"), (int, bool)) else None,
                        "debug_type": type(obj.get("debug")).__name__,
                        "debug_keys": sorted(obj["debug"].keys()) if isinstance(obj.get("debug"), dict) else None,
                    })
                else:
                    record["response_type"] = type(obj).__name__
            except Exception as exc:
                record["error_type"] = type(exc).__name__
            observed.append(record)

        page.on("response", on_response)
        try:
            response = page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            print("Browser page HTTP:", response.status if response else "no-response", flush=True)
            page.wait_for_timeout(10000)
            print("Browser page title:", page.title()[:120], flush=True)
            print("Browser coinsale response count:", len(observed), flush=True)
            for record in observed:
                print("Browser coinsale:", json.dumps(record, ensure_ascii=False, sort_keys=True), flush=True)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
