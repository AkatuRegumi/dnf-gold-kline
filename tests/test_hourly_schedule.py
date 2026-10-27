"""Hourly DNF quote collection invariants, with no network or extra dependencies."""
from datetime import datetime, timezone
from pathlib import Path
import re
import unittest

from collector.collect import regions, pick_regions


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "collect.yml"
TEST_WORKFLOW = ROOT / ".github" / "workflows" / "test.yml"

CRON_TO_GROUP = (
    ("7 * * * *", "group0", 7),
    ("27 * * * *", "group1", 27),
    ("47 * * * *", "group2", 47),
)


class HourlyScheduleContractTest(unittest.TestCase):
    def test_schedule_matches_exact_cron_identity_dispatch(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        schedule_block = content.split("  schedule:", 1)[1].split("  workflow_dispatch:", 1)[0]
        cron_entries = re.findall(r"- cron: '([^']+)'", schedule_block)
        self.assertEqual(cron_entries, [c for c, _, _ in CRON_TO_GROUP])
        for cron, group, _ in CRON_TO_GROUP:
            self.assertIn(f"'{cron}') selected={group} ;;", content)
        self.assertIn("python -m collector.browser_collect --region", content)
        self.assertIn("cancel-in-progress: false", content)

    def test_every_hour_covers_exactly_nine_regions_once(self):
        opts = regions()
        expected = {r["id"] for r in opts}
        self.assertEqual(len(expected), 9)
        for hour in range(24):
            total = []
            for _, group, minute in CRON_TO_GROUP:
                at = datetime(2026, 10, 28, hour, minute, tzinfo=timezone.utc)
                explicit = pick_regions(opts, group, at)
                fallback = pick_regions(opts, "scheduled", at)
                self.assertEqual(fallback, explicit)
                self.assertEqual(len(explicit), 3)
                total.extend(x["id"] for x in explicit)
            self.assertEqual(set(total), expected)
            self.assertEqual(len(total), 9)

    def test_high_volume_data_commits_do_not_trigger_full_browser_ci(self):
        content = TEST_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("paths-ignore:", content)
        self.assertIn("'docs/data/**'", content)
        self.assertIn("  pull_request:", content)


if __name__ == "__main__":
    unittest.main()
