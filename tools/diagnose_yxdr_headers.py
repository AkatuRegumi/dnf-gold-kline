"""Small, non-evasive comparison of two ordinary requests for one public YXDR channel.

Only compares ordinary Accept/Origin header shapes. No login, token replay,
client fingerprint spoofing, retries, CAPTCHA bypass, or raw response logging.
Uses the site's public page session and fresh documented page-provided params.
"""
from __future__ import annotations

from http.cookiejar import CookieJar
from urllib.request import Request, build_opener, HTTPCookieProcessor
import hashlib
import json
import time

from collector.collect import fetch_text, fetch_json
from collector.market import BASE, assignment, script_url

PAGE = BASE + "/bijiaqi/dnf/youxibi/kua7"
ENDPOINT = BASE + "/bijia/coinsale"
TOKEN_ENDPOINT = BASE + "/bijia/coinsalesecret"


def request_variant(opener, payload: dict, normal_page_headers: bool):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/javascript, */*; q=0.01" if normal_page_headers else "application/json",
        "Referer": PAGE,
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (compatible; DNF-Gold-Kline/0.2)",
    }
    if normal_page_headers:
        headers["Origin"] = BASE
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    req = Request(ENDPOINT, data=body, method="POST", headers=headers)
    with opener.open(req, timeout=20) as response:
        obj = json.load(response)
        return response.status, obj


def safe_report(label: str, http: int, response):
    if not isinstance(response, dict):
        print(f"{label}: HTTP={http} unexpected={type(response).__name__}", flush=True)
        return
    rows = response.get("data")
    debug = response.get("debug")
    print(f"{label}: HTTP={http} success={response.get('success')!r} "
          f"rows={len(rows) if isinstance(rows, list) else None} "
          f"data_type={type(rows).__name__} debug_type={type(debug).__name__} "
          f"debug_length={len(debug) if isinstance(debug, str) else None}", flush=True)


def main():
    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    html = fetch_text(opener, PAGE)
    source = fetch_text(opener, script_url(html))
    channels = assignment(source, "bijiaqiChanels")
    meta = assignment(source, "bijiaqiResult")
    target = next((c for c in channels if
                   json.loads(c["data"]).get("PfId") == 44), None)
    if target is None or not isinstance(meta, dict) or meta.get("GId") != 1838:
        raise RuntimeError("No matching public quote channel; stop without probing alternatives.")
    params = json.loads(target["data"])
    print("Target channel:", params.get("PfName"), "PfId:", params.get("PfId"), flush=True)
    print("Cookies received from public page:", len(jar), flush=True)
    for label, as_page in (("baseline", False), ("page_header_shape", True)):
        # A fresh token makes the comparison independent of one-time token usage.
        token = fetch_json(opener, TOKEN_ENDPOINT, {"GId": 1838, "GsId": meta["GsId"]}, PAGE)
        if not isinstance(token, dict) or not token.get("secret") or not token.get("time"):
            raise RuntimeError("No ordinary public token; stop.")
        signature = hashlib.md5(
            f'{token["secret"]}_{params["PfId"]}_{target["sign"]}'.encode("utf-8")
        ).hexdigest()
        payload = {
            "data": target["data"], "sign": target["sign"], "cross": 0,
            "dnfCross": 1, "time": token["time"], "secret": signature,
        }
        http, response = request_variant(opener, payload, as_page)
        safe_report(label, http, response)
        if label == "baseline":
            time.sleep(3)
    print("One-shot comparison complete. Success=0 is not authorization to keep retrying.", flush=True)


if __name__ == "__main__":
    main()
