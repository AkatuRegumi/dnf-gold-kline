"""No duplicate real snapshots within the same UTC hour after external dispatch.

These tests never contact YXDR and do not require Playwright.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from collector.browser_collect import captured_this_hour
from collector.collect import save_sample, save_attempt

def sample(region, at, quality="usable"):
    return {"region":region,"observed_at":at.isoformat(timespec="seconds"),
            "quality":quality,"best_ratio":91.0,"offers_count":30}

class HourlyIdempotencyTest(unittest.TestCase):
    def test_once_per_hour_even_for_partial_or_old_observed_quote(self):
        with TemporaryDirectory() as tmp:
            dest=Path(tmp)
            first=datetime(2026,11,1,10,7,tzinfo=timezone.utc)
            save_sample("kua2",sample("kua2",first),dest)
            self.assertTrue(captured_this_hour("kua2",dest,now=first+timedelta(minutes=50)))
            self.assertFalse(captured_this_hour("kua2",dest,now=first+timedelta(hours=1)))
            self.assertFalse(captured_this_hour("kua3a",dest,now=first+timedelta(minutes=5)))
            save_sample("kua3a",sample("kua3a",first,quality="partial"),dest)
            self.assertTrue(captured_this_hour("kua3a",dest,now=first+timedelta(minutes=5)))

    def test_beijing_same_hour_without_local_timezone_assumptions(self):
        with TemporaryDirectory() as tmp:
            dest=Path(tmp)
            local_at=datetime(2026,11,2,0,5,tzinfo=timezone(timedelta(hours=8)))
            save_sample("kua2",sample("kua2",local_at),dest)
            self.assertTrue(captured_this_hour("kua2",dest,
               now=datetime(2026,11,1,16,30,tzinfo=timezone.utc)))
            self.assertFalse(captured_this_hour("kua2",dest,
               now=datetime(2026,11,1,17,5,tzinfo=timezone.utc)))

    def test_failures_do_not_fabricate_completed_quote(self):
        with TemporaryDirectory() as tmp:
            dest=Path(tmp)
            save_attempt("kua2","failed",dest,reason="BrowserTimeout")
            self.assertFalse(captured_this_hour("kua2",dest,
               now=datetime(2026,11,1,12,5,tzinfo=timezone.utc)))

    def test_bad_history_fails_closed(self):
        with TemporaryDirectory() as tmp:
            dest=Path(tmp)
            p=dest/"kua2.json"
            p.write_text(json.dumps({"region":"kua3a","samples":[
                {"observed_at":"2026-11-01T12:05:00+00:00"}]}))
            with self.assertRaisesRegex(ValueError,"Invalid region"):
                captured_this_hour("kua2",dest,
                  now=datetime(2026,11,1,12,10,tzinfo=timezone.utc))
            p.write_text(json.dumps({"region":"kua2","samples":[
                {"observed_at":"2026-11-01T12:05:00"}]}))
            with self.assertRaisesRegex(ValueError,"lacks timezone"):
                captured_this_hour("kua2",dest,
                  now=datetime(2026,11,1,12,10,tzinfo=timezone.utc))

    def test_requires_timezone_aware_slot(self):
        with TemporaryDirectory() as tmp:
            dest=Path(tmp)
            save_sample("kua2",sample("kua2",
                datetime(2026,11,1,12,5,tzinfo=timezone.utc)),dest)
            with self.assertRaisesRegex(ValueError,"timezone-aware"):
                captured_this_hour("kua2",dest,now=datetime(2026,11,1,12,10))

if __name__ == "__main__":
    unittest.main()
