"""Local-only Chrome smoke test for native Canvas hover interactions.

No calls to the price provider. Loads the static /docs site from 127.0.0.1
and verifies pointer tooltip, guides, region and period switching.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parents[1] / "docs"


def main():
    handler = partial(SimpleHTTPRequestHandler, directory=str(DOCS))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    browser = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/index.html?region=kua2")
            page.wait_for_function("document.getElementById('count').textContent !== '0'")
            canvas = page.locator("#chart")
            canvas.hover(position={"x": 300, "y": 170})
            assert page.locator("#chart-hover").is_visible(), "hover card should appear"
            assert page.locator("#chart-cross-v").is_visible(), "vertical guide should appear"
            assert page.locator("#chart-cross-h").is_visible(), "horizontal guide should appear"
            assert page.locator("#chart-cursor-price").is_visible(), "pointer price should appear"
            hover_text = page.locator("#chart-hover").inner_text()
            assert "开盘" in hover_text and "收盘" in hover_text and "合格采样" in hover_text, hover_text
            page.mouse.move(3, 3)
            assert not page.locator("#chart-hover").is_visible(), "hover should dismiss"
            page.locator("#region-select").select_option("kua7")
            page.wait_for_function("document.getElementById('chart-title').textContent.includes('跨七')")
            assert not page.locator("#chart-hover").is_visible(), "region switch should clear old hover"
            page.locator('#period button[data-kind="week"]').click()
            assert page.locator('#period button[data-kind="week"]').get_attribute("aria-pressed") == "true"
            assert not errors, "browser errors: " + "; ".join(errors)
            print("PASS: real Chrome Canvas hover/crosshair/label/clear/region/period")
            browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
