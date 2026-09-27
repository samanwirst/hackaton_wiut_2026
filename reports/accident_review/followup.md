# Remaining collision candidates: scoped follow-up

On 2026-09-27, AI-assisted inspection revisited the remaining nine accident segments
(ten raw track-pair firings; two C3897 firings merge). The reference is
`reports/original_gpu/predictions-reviewed.json`, not an organiser annotation.
This review did **not** justify describing these predictions as confirmed crashes.

| Video | Raw candidate start | Observation in the sampled window |
|---|---:|---|
| C3896 | 227.56 s | Traffic closes up in a queue; no clear impact is visible. |
| C3896 | 274.74 s | Adjacent traffic and occlusion; contact remains unconfirmed. |
| C3897 | 55.79 s | A passing bus occludes vehicles next to a stationary vehicle. |
| C3897 | 60.46 s | Vehicles queue behind the crossing; the bus moves out of the foreground. |
| C3897 | 222.09 s | Vehicles pass pedestrians at the crossing; no visible impact response. |
| C3897 | 224.96 s | Parallel queues close up near an overhead structure. |
| C3902 | 1.47 s | A van approaches a stationary car; visible separation around the proposed onset. |
| C3902 | 32.43 s | A white car turns toward the kerb while the pedestrian continues on the pavement. |
| C3902 | 76.41 s | Vehicles slow and stop in a red-light queue. |
| C3902 | 165.30 s | Dense traffic closes up; foreground structures obscure parts of the vehicles. |

Most overviews cover approximately ten seconds, beginning two seconds before the candidate,
at **2 fps**; the first C3902 candidate also has a separate 0–8 s overview at 1 fps.
Timestamp labels show relative sampling time plus the seek offset and are approximate.
For C3902, frames 30–59 (1.001–1.969 s at 30000/1001 fps) were additionally inspected at
full frame rate around the proposed onset. This is only a one-second dense window, not a
full-rate review of the whole event or video. Overviews and diagnostic track arrays are
retained in the ignored local `.cache/accident-review.Y2Z3FT/` directory.

The two illustrative overview crops packaged here are
[queue/occlusion in C3897](C3897_60.46_overview.jpg) and
[turning car beside a pedestrian in C3902](C3902_32.43_overview.jpg).
Their labels must not be used as precise event boundaries.

These observations expose the limit of image-space proximity plus deceleration: ordinary
queueing, perspective overlap and occlusion can imitate the rule's crash signature. They do
not create exhaustive negative labels, measure recall, or prove the absence of very brief
contact between sampled frames. No event F1 or collision precision is claimed from them.
The final scene/signal correction addresses calibration, not this unresolved collision-model
limitation; an independently labelled development set and a learned contact verifier remain
the next substantive model improvements.
