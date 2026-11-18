"""GitHub primary + fallback cron sampling contracts (no network dependencies).

Two scheduled events per hourly group increase *attempts*, not the maximum
number of persisted quotes (collector/browser_collect.py enforces per-region
hourly idempotency).
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re
import unittest

from collector.collect import regions, pick_regions


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "collect.yml"
TEST_WORKFLOW = ROOT / ".github" / "workflows" / "test.yml"

# Primary and fallback cron expressions are pinned to explicit, nonoverlapping
# cross-region groups even if GitHub starts the job late.
CRON_TO_GROUP = (
    ("7 * * * *", "group0", 7),
    ("17 * * * *", "group0", 17),
    ("27 * * * *", "group1", 27),
    ("37 * * * *", "group1", 37),
    ("47 * * * *", "group2", 47),
    ("57 * * * *", "group2", 57),
)


class HourlyScheduleContractTest(unittest.TestCase):
    def test_schedule_matches_exact_cron_identity_dispatch(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        schedule_block = content.split("  schedule:", 1)[1].split("  workflow_dispatch:", 1)[0]
        cron_entries = re.findall(r"- cron: '([^']+)'", schedule_block)
        self.assertEqual(cron_entries, [c for c, _, _ in CRON_TO_GROUP])
        # Use workflow event.schedule rather than delayed runner minute.
        self.assertIn("EVENT_SCHEDULE: ${{ github.event.schedule }}", content)
        for group in ("group0", "group1", "group2"):
            crons = [c for c, g, _ in CRON_TO_GROUP if g == group]
            self.assertEqual(len(crons), 2)
            shell_case = "|".join(f"'{c}'" for c in crons)
            self.assertIn(f"{shell_case}) selected={group} ;;", content)
        self.assertIn("python -m collector.browser_collect --region", content)
        self.assertIn("cancel-in-progress: false", content)

    def test_each_hour_two_chances_for_every_region_but_only_nine_unique_regions(self):
        options = regions()
        expected = {r["id"] for r in options}
        self.assertEqual(len(expected), 9)
        for hour in range(24):
            selected = []
            for _, group, minute in CRON_TO_GROUP:
                at = datetime(2026, 11, 18, hour, minute, tzinfo=timezone.utc)
                explicit = pick_regions(options, group, at)
                fallback = pick_regions(options, "scheduled", at)
                self.assertEqual(fallback, explicit)
                self.assertEqual(len(explicit), 3)
                selected.extend(r["id"] for r in explicit)
            counts = Counter(selected)
            self.assertEqual(set(counts), expected)
            self.assertEqual(set(counts.values()), {2})

    def test_canonical_collector_prevents_duplicate_actual_requests(self):
        content = (ROOT / "collector" / "browser_collect.py").read_text(encoding="utf-8")
        self.assertIn('if captured_this_hour(region["id"], data_dir):', content)
        self.assertIn("continue\n", content)
        self.assertIn("save_sample(region['id'], sample, data_dir)", content)

    def test_high_volume_data_commits_do_not_trigger_full_browser_ci(self):
        content = TEST_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("paths-ignore:", content)
        self.assertIn("'docs/data/**'", content)
        self.assertIn("  pull_request:", content)


if __name__ == "__main__":
    unittest.main()
