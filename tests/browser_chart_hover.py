"""Local-only browser smoke for the DNF terminal interactions.

A minimal ECharts API stub avoids network/CDN dependence in CI. Real chart math,
period switching and data-quality behavior are separately tested in Node.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parents[1] / "docs"
ECHARTS_STUB = """
(function(){
  const instances = new WeakMap();
  window.echarts = {
    init(el) {
      const instance = {
        _option:null,
        setOption(option) {
          this._option=option;
          el.dataset.series=(option.series||[]).map(s=>s.type).join(',');
          el.dataset.points=String(option.series?.[0]?.data?.length||0);
        },
        clear() {this._option=null;el.dataset.series='';},
        resize() {},
        dispose() {}
      };
      instances.set(el,instance);
      return instance;
    },
    getInstanceByDom(el) {return instances.get(el);}
  };
})();
"""


def main():
    handler = partial(SimpleHTTPRequestHandler, directory=str(DOCS))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1350, "height": 920})
            page.route("**/echarts.min.js", lambda route: route.fulfill(
                status=200, content_type="application/javascript", body=ECHARTS_STUB))
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{server.server_port}/index.html?region=kua2")
            page.wait_for_function("document.getElementById('count').textContent !== '—'")
            assert "跨二" in page.locator("#region-name").inner_text()
            assert page.locator("#main-chart").get_attribute("data-series").startswith("candlestick")
            assert int(page.locator("#main-chart").get_attribute("data-points")) >= 1
            assert page.locator("#overview button").count() == 9
            assert page.locator("#ticker button").count() == 9
            assert page.locator("#tape .tape-row").count() >= 1
            # Default day candles, with no merged wholesale or partial samples.
            candles = page.evaluate("""() => echarts.getInstanceByDom(
              document.getElementById('main-chart'))._option.series[0].data""")
            assert all(x == '-' or len(x) == 4 for x in candles)
            page.locator('#timeframes button[data-kind="trend"]').click()
            assert page.locator("#main-chart").get_attribute("data-series").startswith("line")
            page.locator('#sub-modes button[data-ind="platforms"]').click()
            assert "bar" in page.locator("#secondary-chart").get_attribute("data-series")
            page.locator("#region-select").select_option("kua7")
            assert "跨七" in page.locator("#region-name").inner_text()
            assert "region=kua7" in page.url
            page.locator('#timeframes button[data-kind="week"]').click()
            assert page.locator("#main-chart").get_attribute("data-series").startswith("candlestick")
            page.locator('#timeframes button[data-kind="day"]').click()
            page.locator('#btn-refresh').click()
            page.wait_for_function("document.getElementById('btn-refresh').disabled === false")
            # Mobile layout maintains usable main chart and region switching.
            page.set_viewport_size({"width": 390, "height": 800})
            page.locator('#overview button[data-region="kua2"]').click()
            assert "跨二" in page.locator("#region-name").inner_text()
            assert page.locator("#main-chart").is_visible()
            assert not errors, "Browser errors: " + "; ".join(errors)
            print("PASS: nine-region ticker, sampled candles, trend, coverage, tape, deep link, refresh, responsive")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
