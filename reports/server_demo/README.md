# Shared-server demo verification

Checked on 27 September 2026. Public app:
<https://trafficwatch.31-130-151-28.sslip.io/>.

The verified flow is MP4 upload → local CPU inference → managed output cache → annotated
playback, event/risk chart, event table and JSON download. No hosted inference API is used.
These are functional checks, not accuracy measurements or a target-GPU benchmark.

| Check | Private SSH preview, mobile | Public HTTPS, desktop |
|---|---|---|
| Input | 120 s, 1280×720, 30 fps | Same input |
| Inference/render elapsed | 172 s | 190 s |
| Output | 17 candidates, 720 sampled risk points | Same counts |
| Progress | Detection, risk, rendering, ready | All four stages |
| Playback | 120 s input/output, seek to 90 s | Same |
| JSON download | HTTP 200 | HTTP 200 |
| 124 s upload | Clearly rejected | Clearly rejected |
| Browser errors / horizontal overflow | None | None |

Machine-readable evidence is in `private-mobile.json` and `public-desktop.json`.
The public completion screenshot was visually inspected before inclusion.
HTTPS certificate validation passed without ignoring certificate errors.

## Deployment boundary and follow-up

- Only a new dedicated Compose project was added. Model: 0.75 CPU, 2 GiB RAM including
  swap, unprivileged user, read-only image, internal network, no host port or Docker socket.
- A small separate Nginx gateway routes through the existing proxy using unique labels.
  Existing proxy configuration and unrelated containers were not restarted or edited.
- The 13 pre-existing containers retained their IDs, start times and restart counts at the
  private-start checkpoint. Both existing sites returned HTTP 200 during inference checks.
  These observations do not establish a guarantee of zero performance impact.
- Cache cleanup runs hourly with a six-hour age limit; logs rotate. Monitor disk capacity
  and keep the host running through judging. Resource limits are not a service-level guarantee.
- The captain considered longer uploads, then explicitly chose the task-sufficient
  **2-minute / 500 MiB** policy. The original verified image was restored; the public
  configuration again advertises two minutes. This cap never applies to offline evaluation.

The initial local Docker config ID is
`sha256:5f4cefa959cdf1185e5c8dfdcc2923fcf909874b6a4e8dd52ca633dff9931b40`.
The imported server manifest ID is
`sha256:88ca83f166e08f5d372003c8125ee75135425e2ab71286836e86883db52fe214`.
The differing IDs reflect image-store conversion: all RootFS layer hashes and runtime-critical
configuration fields were compared and matched. The app, inference source/configuration and
YOLO11n weights are unchanged from the previously verified package.

The table above records the initial 1.5 GiB staging configuration. Subsequent embedded
browser checks exposed two distinct failures: a client `ERR_NETWORK_CHANGED` interrupted
the event stream, and a later repeated request reached the demo's cgroup memory limit.
Docker recorded an OOM event and restarted only that demo container. A healthy status after
restart did not mean the interrupted request had succeeded.

Commit `4a79c08` raises only the isolated demo's memory limit to 2 GiB (the host had about
3.4 GiB available while the app was idle), sets `OPENCV_FFMPEG_THREADS=1` and
`MALLOC_ARENA_MAX=2`, and retains the 0.75 CPU limit. Model code, weights, sampling and
official evaluation files are unchanged. Existing sites continued to return HTTP 200.
The follow-up two-minute upload inside the public website passed in a fresh browser context
at 390×844: **198 s**, all four progress stages, 17 candidates / 720 sampled risk points,
120-second input/output, playback/seek to 90 s, chart/table and HTTP-200 JSON download,
no JavaScript errors or horizontal overflow. See `public-embedded-mobile.json` and its
visually inspected screenshot. During that request, the observed cgroup peak was
1,000,558,592 bytes, with zero OOM events and zero restarts. This is a bounded smoke test,
not a prolonged load/availability guarantee. Interrupted client connections must be retried.

A second consecutive two-minute upload through the public queued API completed in **182 s**:
17 candidates, 720 risk samples, downloaded JSON and a 6,556,907-byte annotated video.
See `public-warm-repeat.json`; this is an API repeat, not a second independent UI test.
After both requests the container still had zero OOM events and zero restarts; observed peak
memory was **1,402,064,896 bytes**. The demo and both existing sites returned HTTP 200.
The public desktop/mobile website checks also covered all four sample videos, image assets,
event/risk seeking, range requests and delayed-selection behaviour without page errors.

The final read-only deployment audit compared all **30 runtime source/configuration/weight
files** against both the verified package manifest and the current checkout: every SHA-256
matched. All **13 pre-existing containers** retained their original IDs, start times, running
states and restart counts. The server runs the documented lightweight CPU upload profile;
the complete organiser evaluation package, including `solution.py`, lives in the repository.
The web demo is not a T4 evaluation environment or a substitute for that offline package.
