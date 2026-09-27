"""Upload an explicit test clip to a running demo and verify the complete browser flow.

This performs inference and writes demo output/cache files. Start a local prepared
Space separately; pass a public URL only when authorised to test that deployment.
The browser is owned by this check and is always closed, including on failure.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import shutil

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:7861/")
    parser.add_argument("--browser", default=shutil.which("chromium") or shutil.which("google-chrome"))
    parser.add_argument("--out", type=Path, default=Path(".cache/demo-browser-qa"))
    parser.add_argument("--timeout", type=int, default=600, help="Maximum inference wait in seconds")
    parser.add_argument("--width", type=int, default=1440, help="Browser viewport width; use 390 for mobile")
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--reject-video", type=Path, help="Optional MP4 longer than 120.1 s; verify visible rejection")
    args = parser.parse_args()
    assert args.video.is_file() and args.video.suffix.lower() == ".mp4", args.video
    if args.reject_video:
        assert args.reject_video.is_file() and args.reject_video.suffix.lower() == ".mp4", args.reject_video
    args.out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.browser, headless=True,
                                            args=["--disable-dev-shm-usage", "--disable-gpu"])
        try:
            page = browser.new_page(viewport={"width": args.width, "height": args.height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(args.base_url, wait_until="networkidle")
            button = page.get_by_role("button", name="Detect events", exact=True)
            button.wait_for(state="visible")
            assert "2 minutes / 500 MB" in page.locator("body").inner_text()
            assert "Model predictions, not verified labels" in page.locator("body").inner_text()
            assert "not empirically calibrated probabilities" in page.locator("body").inner_text()
            print(page.locator("body").inner_text()[:2000], flush=True)
            page.screenshot(path=str(args.out / "initial.png"), full_page=True)
            assert not errors, errors

            page.locator('input[type="file"]').first.set_input_files(str(args.video.resolve()))
            page.wait_for_function("document.querySelector('video')?.readyState >= 1", timeout=60000)
            page.evaluate("""() => {
                window.__demoProgress = new Set();
                window.__demoObserver = new MutationObserver(() => {
                    const text = document.body.innerText;
                    for (const stage of ['Detecting and tracking', 'Part B: accident risk', 'Rendering', 'Ready']) {
                        if (text.includes(stage)) window.__demoProgress.add(stage);
                    }
                });
                window.__demoObserver.observe(document.body, {subtree: true, childList: true, characterData: true});
            }""")
            button.click()
            page.get_by_text(re.compile(r"processed in \d+ s on CPU")).wait_for(
                state="visible", timeout=args.timeout * 1000)
            page.wait_for_function("""() => {
                const videos = [...document.querySelectorAll('video')];
                return videos.length === 2 && videos.every(v => v.readyState >= 2 && v.duration > 0);
            }""", timeout=60000)
            page.locator(".js-plotly-plot .main-svg").first.wait_for(state="visible", timeout=60000)
            link = page.locator('a[href*="events.json"]').first
            link.wait_for(state="visible")
            response = page.request.get(link.get_attribute("href"))
            assert response.status == 200, response.status
            payload = response.json()
            assert set(payload) == {"events", "risk"}
            assert payload["risk"] and all(
                math.isfinite(t) and math.isfinite(value) and 0 <= value <= 1
                for t, value in payload["risk"]
            )
            assert all(a[0] < b[0] for a, b in zip(payload["risk"], payload["risk"][1:]))
            assert all(0 <= start < end for start, end, _ in payload["events"])
            for header in ("start_sec", "end_sec", "label", "length_s"):
                assert page.get_by_text(header, exact=True).count() >= 1, header
            for _, _, label in payload["events"]:
                assert page.get_by_text(label, exact=True).count() >= 1, label

            output = page.locator("video").nth(1)
            durations = page.locator("video").evaluate_all("videos => videos.map(v => v.duration)")
            assert abs(durations[0] - durations[1]) < 0.25, durations
            output.evaluate("v => v.play()")
            page.wait_for_function("document.querySelectorAll('video')[1].currentTime > 0.1", timeout=30000)
            target = durations[1] * 0.75
            output.evaluate("(v, t) => {v.pause(); v.currentTime = t;}", target)
            page.wait_for_function("""t => {
                const v = document.querySelectorAll('video')[1];
                return !v.seeking && v.readyState >= 2 && Math.abs(v.currentTime - t) < 0.2;
            }""", arg=target, timeout=30000)
            stages = page.evaluate("() => {window.__demoObserver.disconnect(); return [...window.__demoProgress];}")
            assert any(stage in stages for stage in ("Detecting and tracking", "Rendering")), stages
            summary = page.get_by_text(re.compile(r"processed in \d+ s on CPU")).inner_text()
            assert f"{len(payload['events'])} events" in summary
            assert not errors, errors
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(args.out / "completed.png"), full_page=True)
            evidence = {"viewport": {"width": args.width, "height": args.height},
                        "summary": summary, "events": len(payload["events"]),
                        "risk_samples": len(payload["risk"]), "video_durations": durations,
                        "progress_stages": stages, "json_status": response.status,
                        "seek_time": output.evaluate("v => v.currentTime"), "page_errors": errors}
            if args.reject_video:
                page.reload(wait_until="networkidle")
                page.locator('input[type="file"]').first.set_input_files(str(args.reject_video.resolve()))
                page.wait_for_function("document.querySelector('video')?.readyState >= 1", timeout=60000)
                page.get_by_role("button", name="Detect events", exact=True).click()
                page.wait_for_function(
                    "document.body.innerText.includes('The public demo accepts clips up to 2 minutes.')",
                    timeout=30000,
                )
                rejection = page.get_by_text("The public demo accepts clips up to 2 minutes.", exact=True)
                rejection.wait_for(state="visible", timeout=10000)
                # A newly mounted Gradio toast starts transparent; DOM presence alone
                # does not prove a visitor can read the error message.
                page.wait_for_function("""e => {
                    for (let p = e; p; p = p.parentElement) {
                        if (Number(getComputedStyle(p).opacity) < 0.99) return false;
                    }
                    return true;
                }""", arg=rejection.element_handle(), timeout=10000)
                page.screenshot(path=str(args.out / "rejection-message.png"))
                assert page.locator("video").count() == 1
                assert page.locator('a[href*="events.json"]').count() == 0
                assert not errors, errors
                page.screenshot(path=str(args.out / "over-length-rejected.png"), full_page=True)
                evidence["over_length_rejected_in_browser"] = True
            (args.out / "verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
            print(json.dumps(evidence, indent=2), flush=True)
        except Exception:
            if "page" in locals():
                page.screenshot(path=str(args.out / "failure.png"), full_page=True)
            raise
        finally:
            browser.close()
    print("PASS: actual upload, visible progress, playback/seeking, Plotly, event table and JSON download.")


if __name__ == "__main__":
    main()
