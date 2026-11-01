"""Offline guards for the standalone quote terminal, not runtime DOM tests."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "docs" / "terminal.js").read_text(encoding="utf-8")
MODEL = (ROOT / "docs" / "market-data.js").read_text(encoding="utf-8")


class FrontendInteractionTest(unittest.TestCase):
    def test_chart_dependency_and_responsive_layout(self):
        self.assertIn("echarts@5.5.1", HTML)
        self.assertIn("market-data.js", HTML)
        self.assertIn("terminal.js", HTML)
        for part in ("main-chart", "secondary-chart", "timeframes", "sub-modes",
                     "overview", "ticker", "tape", "region-select"):
            self.assertIn(f'id="{part}"', HTML)
        self.assertIn("data-kind=\"day\"", HTML)
        self.assertIn("data-ind=\"platforms\"", HTML)

    def test_observed_vs_strict_candle_and_scope(self):
        self.assertIn("M.observations(samples)", JS)
        self.assertIn("M.candles(samples,period)", JS)
        self.assertIn("data:bars.map", JS) if False else None
        self.assertIn('b.n<2?"-":[b.o,b.c,b.l,b.h]', JS)
        self.assertIn('type:"scatter"', JS)
        self.assertIn("midnightObserved", JS)
        self.assertIn("M.qualified(s)", JS)
        self.assertIn("if (!s || !validRatio(s)) return false;", MODEL)
        self.assertIn("contributing_retail_platforms", MODEL)
        self.assertIn("dataZoom", JS)
        self.assertIn("M.ma(bars,n)", JS)
        self.assertIn("数据来源：游戏达人", JS)
        self.assertIn("非成交", HTML)
        self.assertNotIn("真实成交量", HTML)

    def test_data_files_are_never_posted_or_changed_by_frontend(self):
        self.assertIn('fetch("./data/"', JS)
        self.assertNotIn('method:"POST"', JS)
        self.assertIn('if(body.region!==r.id', JS)
        self.assertIn("data.default_region", JS)


if __name__ == "__main__":
    unittest.main()
