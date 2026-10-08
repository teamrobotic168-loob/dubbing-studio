#!/usr/bin/env python3
"""Draw the icons of the installable app (static/icons/*.png) from the logo - run it only when the logo changes.

    python tools/make_icons.py

The logo is the one of the favicon in static/index.html: a violet -> cyan square with five white bars.  The PNGs are drawn by Chromium
(Playwright, the same one the UI tests use), so they are exactly what the browser shows.  Files:

    icon-192.png            192 x 192   rounded square, transparent corners        ("any")
    icon-512.png            512 x 512   the same, big                              ("any")
    icon-maskable-512.png   512 x 512   full square, the bars inside the safe zone  ("maskable": Android / Windows cut their own shape)
    apple-touch-icon.png    180 x 180   full square (iOS / macOS Safari round it themselves)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "icons"

# (file, pixels, rounded corners?, size of the bars: 1 = as in the favicon)
ICONS = (
    ("icon-192.png", 192, True, 1.0),
    ("icon-512.png", 512, True, 1.0),
    ("icon-maskable-512.png", 512, False, 0.8),
    ("apple-touch-icon.png", 180, False, 0.9),
)


def svg(px: int, rounded: bool, bars: float) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" viewBox="0 0 64 64">'
            '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7c6cff"/><stop offset="1" stop-color="#22d3ee"/></linearGradient></defs>'
            f'<rect width="64" height="64" rx="{16 if rounded else 0}" fill="url(#g)"/>'
            f'<g stroke="white" stroke-width="5" stroke-linecap="round" fill="none" transform="translate(32 32) scale({bars}) translate(-32 -32)">'
            '<path d="M16 28v8M24 20v24M32 14v36M40 22v20M48 28v8"/></g></svg>')


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is needed to draw the icons:  pip install playwright && python -m playwright install chromium")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        for name, px, rounded, bars in ICONS:
            page.set_viewport_size({"width": px, "height": px})
            page.set_content(f'<!doctype html><html><body style="margin:0;background:transparent">{svg(px, rounded, bars)}</body></html>')
            page.screenshot(path=str(OUT / name), omit_background=True, clip={"x": 0, "y": 0, "width": px, "height": px})
            print(f"  {name:<24} {px}x{px}  {(OUT / name).stat().st_size:>6} bytes")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
