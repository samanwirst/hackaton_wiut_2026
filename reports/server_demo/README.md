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

## Deployment boundary

- Only a new dedicated Compose project was added. Model: 0.75 CPU, 1.5 GiB RAM including
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
