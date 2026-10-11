"""Offline regression guards for native Canvas quote interactions."""
from pathlib import Path
import unittest


HTML = (Path(__file__).resolve().parents[1] / "docs" / "index.html").read_text(encoding="utf-8")


class FrontendInteractionTest(unittest.TestCase):
    def test_native_canvas_hover_and_crosshair(self):
        self.assertIn('id="chart-hover"', HTML)
        self.assertIn('id="chart-cross-v"', HTML)
        self.assertIn('id="chart-cross-h"', HTML)
        self.assertIn('id="chart-cursor-price"', HTML)
        self.assertIn("canvas.onpointermove=handlePointer;", HTML)
        self.assertIn("canvas.onpointerleave=", HTML)
        self.assertIn('canvas.onkeydown=ev=>', HTML)
        self.assertIn('hover.style.left=', HTML)
        self.assertIn('hover.style.top=', HTML)

    def test_region_switch_resets_old_hover_and_partial_stays_filtered(self):
        self.assertIn("for(const overlay of [hover,crossV,crossH,cursorPrice])overlay.hidden=true;", HTML)
        self.assertIn("canvas.onpointermove=null;", HTML)
        self.assertIn("if(!reliable||!Number.isFinite(ratio)||ratio<=0)continue;", HTML)
        self.assertIn("const reliable=qualified(s);", HTML)
        self.assertIn("resetView();", HTML)
        self.assertIn("hover.textContent=d.date+", HTML)


if __name__ == "__main__":
    unittest.main()
