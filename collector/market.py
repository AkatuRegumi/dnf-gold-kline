"""Validation and aggregation for publicly listed DNF gold offers.

A ratio is 10,000 gold / CNY (万金币/元). No executed trade prices.
"""
from __future__ import annotations

import json
import math
import re
from html import unescape
from urllib.parse import urljoin

BASE = "https://www.yxdr.com"
CROSS_2 = BASE + "/bijiaqi/dnf/youxibi/kua2"


def script_url(html: str) -> str:
    match = re.search(r'<script\b[^>]*\bsrc=["\']([^"\']*CoinSale_yxb_[^"\']+)["\']', html, re.I)
    if not match:
        raise ValueError("网页缺少 YXDR 金币通道脚本 CoinSale_yxb_")
    url = urljoin(BASE + "/", unescape(match.group(1)))
    if not url.startswith(BASE + "/"):
        raise ValueError("拒绝从非 YXDR 域名加载通道脚本")
    return url


def assignment(source: str, name: str):
    """Parse JSON following a JS assignment, without executing untrusted JS."""
    match = re.search(r"(?:window\.)?" + re.escape(name) + r"\s*=\s*", source)
    if not match:
        raise ValueError(f"脚本缺少 {name}")
    value, _ = json.JSONDecoder().raw_decode(source[match.end():].lstrip("\ufeff \t\r\n"))
    return value


def listing(offer: dict, platform: str) -> dict | None:
    """One verifiable listed lot; never multiply Amount by Number.

    The site's 'Amount' is 10,000-gold units and 'Money' is CNY.
    Unknown inventory (-1) is excluded from bulk-quote calculations.
    """
    try:
        amount = float(offer.get("Amount", 0))
        money = float(offer.get("Money", 0))
        price = float(offer.get("Price", 0))
        if not all(math.isfinite(x) for x in (amount, money, price)):
            return None
        if amount <= 0 or money < 5 or price <= 0:
            return None
        ratio = amount / money
        if not 30 <= ratio <= 150:
            return None
        return {
            "platform": platform,
            "ratio": round(ratio, 6),
            "available_wan": amount,
            "lot_cny": money,
            "id": str(offer.get("BuyUrl") or offer.get("ListUrl") or "").strip(),
        }
    except (TypeError, ValueError, OverflowError):
        return None


def clean_listings(rows: list[dict]) -> list[dict]:
    """Avoid double counting identical lots from overlapping server channels."""
    unique: dict[str, dict] = {}
    for r in rows:
        key = r.get("id") or f'{r["platform"]}|{r["ratio"]}|{r["available_wan"]}|{r["lot_cny"]}'
        prev = unique.get(key)
        if prev is None or r["ratio"] > prev["ratio"]:
            unique[key] = r
    return sorted(unique.values(), key=lambda x: x["ratio"], reverse=True)


def depth(rows: list[dict], target_wan: int) -> dict | None:
    """Indicative bulk cost, assuming split orders; not executable liquidity."""
    remaining, spent = float(target_wan), 0.0
    for row in rows:
        if remaining <= 1e-8:
            break
        quantity = min(remaining, float(row["available_wan"]))
        spent += quantity / float(row["ratio"])
        remaining -= quantity
    if remaining > 1e-8 or spent <= 0:
        return None
    return {
        "target_wan": target_wan,
        "quoted_cny": round(spent, 2),
        "ratio_wan_per_cny": round(target_wan / spent, 4),
    }


def summarize(rows: list[dict]) -> dict:
    rows = clean_listings(rows)
    if not rows:
        raise ValueError("没有可核实库存的真实卖家报价，不记录行情")
    return {
        "best_ratio": round(rows[0]["ratio"], 4),
        "offers_count": len(rows),
        "depth": {str(t): depth(rows, t) for t in (30000, 100000, 120000)},
    }


def append_history(history: dict, sample: dict) -> dict:
    items = history.get("samples", [])
    if not isinstance(items, list):
        raise ValueError("历史行情 schema 无效")
    if items and sample["observed_at"] <= items[-1]["observed_at"]:
        raise ValueError("新快照必须晚于上一条")
    return {"schema_version": 1, "region": "kua2", "samples": items + [sample]}
