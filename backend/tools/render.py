"""Render HTML pages to PNG screenshots and extract element manifests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SITE_DIR = ASSETS / "site"
PAGES_DIR = ASSETS / "pages"
MANIFESTS_DIR = ASSETS / "manifests"

VIEWPORT = {"width": 1800, "height": 1200}
DEVICE_SCALE = 2

PAGES: dict[str, dict] = {
    "dashboard": {
        "file": "dashboard.html",
        "elements": [
            "cpu-panel", "memory-panel", "network-panel", "error-panel",
            "latency-mini", "rps-panel",
            "alerts-panel", "deps-panel",
            "latency-panel", "deploy-panel",
            "deploy-v231", "deploy-v232", "deploy-v233", "deploy-v240", "deploy-v240-rb",
            "endpoint-panel", "db-panel",
            "service-table-title", "service-table-panel", "service-table",
            "svc-auth", "svc-gamma",
            "kafka-panel", "connpool-panel",
            "region-panel", "resource-panel",
        ],
    },
    "overview": {
        "file": "overview.html",
        "elements": [
            "overview-uptime", "alerts-card", "alert-count",
            "alert-permission", "alert-apikey", "alert-login",
        ],
    },
    "users": {
        "file": "users.html",
        "elements": ["user-table", "user-guest-admin"],
    },
    "permissions": {
        "file": "permissions.html",
        "elements": [
            "permission-matrix-card", "perm-matrix",
            "perm-guest-admin-write", "perm-guest-admin-delete", "perm-footnote",
        ],
    },
    "api-keys": {
        "file": "api-keys.html",
        "elements": [
            "api-keys-card", "api-keys-table",
            "apikey-no-expiry", "apikey-never", "apikey-footnote",
        ],
    },
    "analytics": {
        "file": "analytics.html",
        "elements": [
            "traffic-chart", "geo-chart", "device-chart", "endpoint-chart",
        ],
    },
    "logs": {
        "file": "logs.html",
        "elements": [
            "audit-log-card", "audit-log-table",
            "log-suspicious-1", "log-suspicious-2", "log-suspicious-3",
        ],
    },
}


def render_page(page, name: str, spec: dict) -> dict:
    html_path = SITE_DIR / spec["file"]
    page.goto(f"file://{html_path}")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(400)

    body = page.evaluate("() => ({ w: document.body.scrollWidth, h: document.body.scrollHeight })")
    full_w, full_h = body["w"], body["h"]

    page.set_viewport_size({"width": full_w, "height": full_h})
    page.wait_for_timeout(200)

    png_path = PAGES_DIR / f"{name}.png"
    page.screenshot(path=str(png_path), full_page=True)

    elements = []
    for eid in spec["elements"]:
        loc = page.locator(f"#{eid}")
        if loc.count() == 0:
            print(f"  WARN: #{eid} not found in {name}")
            continue
        box = loc.bounding_box()
        if box is None:
            print(f"  WARN: #{eid} has no bounding box in {name}")
            continue
        elements.append({
            "id": eid,
            "rect": {
                "x": round(box["x"] / full_w, 4),
                "y": round(box["y"] / full_h, 4),
                "w": round(box["width"] / full_w, 4),
                "h": round(box["height"] / full_h, 4),
            },
        })

    manifest = {
        "stage": name,
        "image": f"{name}.png",
        "width": full_w,
        "height": full_h,
        "elements": elements,
    }

    manifest_path = MANIFESTS_DIR / f"{name}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    return manifest


def main():
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    targets = sys.argv[1:] if len(sys.argv) > 1 else list(PAGES.keys())

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=DEVICE_SCALE,
        )
        page = ctx.new_page()

        for name in targets:
            if name not in PAGES:
                print(f"Unknown page: {name}")
                continue
            print(f"Rendering {name}...")
            manifest = render_page(page, name, PAGES[name])
            n = len(manifest["elements"])
            print(f"  -> {manifest['width']}x{manifest['height']} | {n} elements")

        browser.close()

    print("Done.")


if __name__ == "__main__":
    main()
