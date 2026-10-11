"""Offline, conservative readiness assessment. Does not fetch a website or change cron.

This is a technical signal only, not permission to increase requests to YXDR.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from collector.collect import DATA_DIR, regions

MIN_ATTEMPTS = 12
MIN_SPAN_HOURS = 72
MIN_QUALITY_RATE = 0.80
MIN_CHANNEL_RATE = 0.90
MAX_AGE_HOURS = 36


def evaluate(attempts: list[dict], *, now: datetime) -> dict:
    usable = []
    for entry in attempts[-MIN_ATTEMPTS:]:
        try:
            timestamp = datetime.fromisoformat(entry["attempted_at"])
            if timestamp.tzinfo is None:
                continue
            usable.append((timestamp.astimezone(timezone.utc), entry))
        except (ValueError, KeyError, TypeError):
            continue
    usable.sort(key=lambda row: row[0])
    if len(usable) < MIN_ATTEMPTS:
        return {"status": "insufficient", "attempts": len(usable)}
    start, last = usable[0][0], usable[-1][0]
    age_hours = (now.astimezone(timezone.utc) - last).total_seconds() / 3600
    span_hours = (last - start).total_seconds() / 3600
    if age_hours > MAX_AGE_HOURS or age_hours < -1 or span_hours < MIN_SPAN_HOURS:
        return {"status": "insufficient", "attempts": len(usable),
                "span_hours": round(span_hours, 1), "age_hours": round(age_hours, 1)}
    samples = [item for _, item in usable]
    good = sum(e.get("outcome") == "success" and e.get("quality") == "usable" for e in samples)
    attempted = sum(int(e.get("attempted_channels") or 0) for e in samples)
    succeeded = sum(int(e.get("successful_channels") or 0) for e in samples)
    quality_rate = good / len(samples)
    channel_rate = succeeded / attempted if attempted else 0.0
    result = {
        "attempts": len(samples), "quality_rate": round(quality_rate, 3),
        "channel_rate": round(channel_rate, 3), "span_hours": round(span_hours, 1)
    }
    result["status"] = (
        "candidate" if quality_rate >= MIN_QUALITY_RATE and
        channel_rate >= MIN_CHANNEL_RATE else "hold"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description="Offline DNF quote sampling-health report")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    p = args.data_dir / "collection_status.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    history = data.get("history", {})
    now = datetime.now(timezone.utc)
    for region in regions():
        rid = region["id"]
        result = evaluate(history.get(rid, []), now=now)
        print(rid, result)
    print("Candidate means technical evidence only; it never changes the scheduler.")
    print("Do not increase collection frequency without checking the upstream's access terms.")


if __name__ == "__main__":
    main()
