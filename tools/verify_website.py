"""Browser QA for all original sample results; read-only against the selected server.

Start tools/serve_website.py separately, then run this tool. It compares the served
site with this checkout, not with a claimed deployment version or hidden labels.
"""
import argparse
import json
import shutil
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:8765/")
parser.add_argument("--browser", default=shutil.which("chromium") or shutil.which("google-chrome"))
parser.add_argument("--out", type=Path, default=Path(".cache/browser-qa"))
args = parser.parse_args()
BASE = args.base_url.rstrip("/") + "/"
ROOT = Path(__file__).resolve().parents[1]
args.out.mkdir(parents=True, exist_ok=True)
index = json.loads((ROOT / 'website/data/results_index.json').read_text())
site = json.loads((ROOT / 'website/data/site.json').read_text())
results = {item['video']: json.loads((ROOT / 'website' / item['file']).read_text()) for item in index}
assert set(results) == {'C3896.MP4', 'C3897.MP4', 'C3902.MP4', 'C3905.MP4'}


def check_seek(page, target):
    page.wait_for_function(
        '(t) => { const v = document.querySelector("#resBody video"); '
        'return v && !v.seeking && v.readyState >= 2 && Math.abs(v.currentTime-t) < 2; }',
        arg=target,
        timeout=30000,
    )
    return page.locator('#resBody video').evaluate('(v) => { v.pause(); return v.currentTime; }')


with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=args.browser,
        headless=True,
        args=['--disable-dev-shm-usage', '--disable-gpu'],
    )
    try:
        for width, height, theme in [(1440, 1000, 'light'), (390, 844, 'dark')]:
            page = browser.new_page(viewport={'width': width, 'height': height}, color_scheme=theme)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
            page.goto(BASE, wait_until='networkidle')
            assert page.locator('#resVideo option').count() == 4
            assert page.locator('#edaVideo option').count() == 4
            assert str(sum(item['events'] for item in index)) in page.locator('#heroTiles').inner_text()
            minutes = sum(result['duration'] for result in results.values()) / 60
            assert f'{minutes:.1f} min' in page.locator('#heroTiles').inner_text()
            assert '3840 × 2160 original' in page.locator('#heroSourceCaption').inner_text()
            assert site['metrics']['speed'] in page.locator('#heroTiles').inner_text()
            assert page.locator('#team h2').inner_text() == site['team_name']
            assert page.locator('#teamBody .member h3').all_text_contents() == [
                member['name'] for member in site['team']
            ]
            for position, member in enumerate(site['team']):
                card = page.locator('#teamBody .member').nth(position)
                assert card.locator('.role').text_content() == member['role']
                assert card.locator('p').first.inner_text() == member['contributions']

            for i, item in enumerate(index):
                result = results[item['video']]
                page.select_option('#resVideo', str(i))
                page.wait_for_function(
                    '(src) => { const v=document.querySelector("#resBody video"); '
                    'return v && v.getAttribute("src")===src && v.readyState>=1; }',
                    arg=result['annotated'],
                    timeout=30000,
                )
                assert page.locator('#resBody tr.clickable').count() == item['events']
                assert page.locator('#resBody .tl-bar').count() == item['events']
                assert 'Original' in page.locator('#resBody .result-tiles').inner_text()
                assert 'probability calibration has not been measured' in page.locator('#resBody').inner_text()
                duration = page.locator('#resBody video').evaluate('(v) => v.duration')
                assert abs(duration - result['duration']) < 0.1

                row_i = len(result['events']) // 2
                row_target = max(0, result['events'][row_i][0] - 0.5)
                page.locator('#resBody tr.clickable').nth(row_i).click()
                row_time = check_seek(page, row_target)

                bar = page.locator('#resBody .tl-bar').first
                start = float(re.search(r' (\d+\.\d+) to ', bar.get_attribute('aria-label')).group(1))
                bar.focus()
                bar.press('Enter')
                bar_time = check_seek(page, max(0, start - 0.5))

                risk = page.locator('#resBody .card').filter(
                    has=page.get_by_role('heading', name='Part B: probability that an accident starts within 5 s')
                ).locator('svg rect[fill="transparent"]')
                risk.scroll_into_view_if_needed()
                box = risk.bounding_box()
                risk.click(position={'x': box['width'] * 0.75, 'y': box['height'] * 0.5})
                risk_time = check_seek(page, max(0, result['duration'] * 0.75 - 0.5))

                response = page.request.get(BASE + result['annotated'], headers={'Range': 'bytes=0-1023'})
                assert response.status == 206
                assert len(response.body()) == 1024
                assert response.headers['content-range'].startswith('bytes 0-1023/')

                page.select_option('#edaVideo', str(i))
                assert '3840×2160' in page.locator('#edaBody').inner_text()
                assert 'Original organiser-provided' in page.locator('#edaBody').inner_text()
                assert page.locator('#edaBody .imgs img').count() == 5
                for frame in page.locator('#edaBody .imgs img').all():
                    frame.scroll_into_view_if_needed()
                    page.wait_for_function('(i) => i.complete && i.naturalWidth > 0',
                                           arg=frame.element_handle(), timeout=30000)
                assert not errors, errors
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                print(json.dumps({'width': width, 'video': item['video'], 'events': item['events'],
                                  'duration': duration, 'row_seek': row_time,
                                  'keyboard_seek': bar_time, 'risk_seek': risk_time,
                                  'range_status': response.status}), flush=True)

            page.locator('#eda').scroll_into_view_if_needed()
            page.screenshot(path=str(args.out / f'eda-{width}.png'))
            page.locator('#resBody .player').scroll_into_view_if_needed()
            page.screenshot(path=str(args.out / f'results-{width}.png'))
            page.locator('#reportCases').scroll_into_view_if_needed()
            page.wait_for_function('document.querySelector("#reportCases img").naturalWidth > 0')
            page.locator('#team').scroll_into_view_if_needed()
            page.locator('#team').screenshot(path=str(args.out / f'team-{width}.png'))
            assert not errors, errors
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            page.close()
    finally:
        browser.close()
print('PASS: all four originals, desktop/mobile, EDA and playback, table/keyboard/risk seeks, HTTP ranges, no JS errors/overflow.')
