# Current prepared-demo verification

Local checks on **27 September 2026**, Python 3.11 / CPU / Gradio 5.50.0. These test
the freshly assembled self-contained Space package, not a public deployment.
[`offline.json`](offline.json) records all 34 package-file hashes, input derivation,
input checksums and the network-isolated direct-call results.

## Results

| Check | Observed result |
|---|---|
| Six-second real clip, offline direct call | 0 events, 36 sampled risk points, 36 rendered frames; about 5 s |
| Two-minute real clip, offline direct call | 17 events, 720 sampled risk points, 720 rendered frames; about 47 s |
| Desktop browser, two-minute actual upload | 17 events / 720 risk points; about 49 s; playback and seeking pass |
| Mobile browser, same actual upload | Same counts; about 48 s; playback and seeking pass |
| Mobile browser, six-second upload | 0 events and 36 risk points; empty table, playable video, chart and JSON still work |
| 124-second clip | Rejected offline and in the browser with the visible two-minute limit message |

Both direct-call videos passed complete FFmpeg decoding, preserved duration and
survived managed-cache handoff. The browser checks observed progress, rendered
Plotly timeline/risk charts, event-table headers and labels, HTTP 200 JSON downloads,
playable input/output videos and seeking to 90 seconds. No page JavaScript errors
or horizontal document overflow were observed. Desktop is 1440×1000; mobile is
390×844. The final desktop/mobile screenshots were visually inspected.
The rejection check waits for the toast's fade-in opacity, not merely DOM presence.

Evidence: [desktop JSON](browser-desktop.json), [mobile JSON](browser-mobile.json),
[empty-result JSON](browser-empty.json),
[desktop screenshot](desktop.png), [mobile screenshot](mobile.png),
[visible rejection message](rejection-message.png).

## Reproduce

Use the ordinary development environment and FFmpeg. Assemble into a **new** local
directory with `bash demo/prepare_space.sh <new-directory>`. All source/configuration
and the CPU weight are included; no parent-repository imports are needed.

Derive a two-minute test input from the supplied original, preserving the original:

```bash
ffmpeg -n -i data/samples/C3905.MP4 -t 120 -vf scale=1280:720 -r 30 \
  -an -c:v libx264 -preset veryfast -crf 25 -threads 2 -movflags +faststart \
  .cache/demo-test-120s.mp4
```

The recorded clips use the first 6, 120 and 124 seconds, re-encoded at 1280×720 / 30 fps.
Exact encoded bytes can vary with FFmpeg builds; this report preserves the actual tested
hashes. These clips are local test inputs, not replacements for the original GPU sample runs.

From the assembled package directory, using the development Python environment:

```bash
GRADIO_ANALYTICS_ENABLED=False python -c 'from app import demo, MAX_UPLOAD_BYTES; demo.queue(max_size=8).launch(server_name="127.0.0.1", server_port=7861, max_file_size=MAX_UPLOAD_BYTES)'
```

Then from the repository root:

```bash
python tools/verify_demo.py --video .cache/demo-test-120s.mp4 --out .cache/demo-desktop
python tools/verify_demo.py --video .cache/demo-test-120s.mp4 \
  --width 390 --height 844 --out .cache/demo-mobile
```

Optionally pass `--reject-video <124-second-clip.mp4>` to check visible rejection
after the successful upload. The tool uploads files and runs inference; use a public
`--base-url` only when authorised to test that deployment. Close the owned local
server afterwards. The read-only site check is separate: `tools/verify_website.py`.

## Limits of this evidence

- No public host has been provisioned or tested; the owner deferred publication.
- These are measured local CPU times, not a hosting SLA or target-GPU benchmark.
- The demo uses YOLO11n and sampled risk outputs; the GPU evaluation uses larger models,
  different sampling, original resolution/frame rate and full videos. Counts need not match.
- Events are model candidates and risk scores are not empirically calibrated probabilities.
  The UI explicitly states these limitations; successful UX tests are not accuracy tests.
- The 500 MiB application boundary is covered by unit tests and Gradio's configured HTTP
  limit; a real 500 MiB browser upload has not been stress-tested.
- Six-hour managed-cache expiry is unit-tested; no six-hour live soak is claimed.
